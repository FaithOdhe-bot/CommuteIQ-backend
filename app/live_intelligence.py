"""
CommuteIQ — Live Intelligence Module
live_intelligence.py

Replaces static dataset limitations with real-time internet data.
All sources are FREE — no API keys required except TomTom (free signup).

Four intelligence layers:
  1. TomTom Traffic Flow — real measured road speeds (replaces time-of-day guess)
  2. RSS News Scanner — Nigerian + Kenyan news feeds including Lagos Traffic Radio (LASTMA)
  3. Google News Search — targeted search for floods, accidents, road closures
  4. OSM Road Closures — community road closures + Overpass API construction zones

How it integrates with main.py:
  - get_live_congestion() replaces estimate_congestion() when TomTom key is set
  - get_news_incidents() supplements community reports with news-verified data
  - Results are cached for 10 minutes to avoid hammering free APIs

Setup:
  - TomTom: Sign up free at developer.tomtom.com → get API key → set TOMTOM_API_KEY
  - RSS + Google News: No setup needed — works immediately
"""

import os
import time
import httpx
import asyncio
from typing import Optional
from xml.etree import ElementTree as ET


# ── Configuration ─────────────────────────────────────────────
TOMTOM_API_KEY = os.getenv("TOMTOM_API_KEY", "")   # Free at developer.tomtom.com
CACHE_TTL      = 600   # 10 minutes — how long to cache live results


# ── In-memory caches ──────────────────────────────────────────
_congestion_cache: dict = {}
_news_cache:       dict = {}
_last_news_scan:   float = 0.0


# ── City bounding boxes for TomTom traffic queries ───────────
# TomTom traffic flow accepts a bounding box to return all incidents in an area
CITY_BBOXES = {
    "lagos":         "6.3878,3.0982,6.7063,3.7145",
    "nairobi":       "-1.4441,36.6519,-1.1601,37.0088",
    "abuja":         "8.7640,6.9960,9.3390,7.7300",
    "kano":          "11.8500,8.3700,12.1500,8.7800",
    "ibadan":        "7.2600,3.7900,7.5200,4.1200",
    "port harcourt": "4.6500,6.8900,5.0200,7.2100",
    "mombasa":       "-4.1500,39.5500,-3.9500,39.8500",
    "kisumu":        "-0.1700,34.6800,0.0600,34.9000",
}

# Keyword patterns → report type mapping for news scanning
INCIDENT_KEYWORDS = {
    "accident":     ["accident", "crash", "collision", "overturn", "vehicle",
                     "truck", "lorry", "bus crash", "road crash"],
    "flood":        ["flood", "flooding", "waterlogged", "submerged", "water",
                     "rain", "downpour", "drainage"],
    "road_closure": ["closed", "closure", "blocked", "road block", "diversion",
                     "shutdown", "barricade", "protest", "demonstration"],
    "heavy_traffic":["gridlock", "traffic jam", "gridlock", "standstill",
                     "congestion", "slow moving", "heavy traffic", "bumper"],
    "construction": ["construction", "repair", "pothole", "road work",
                     "rehabilitation", "maintenance"],
}

# Location keywords per city — used to assign news items to correct city
CITY_KEYWORDS = {
    "lagos":         ["lagos", "lekki", "ikeja", "ikorodu", "surulere", "victoria island",
                      "oshodi", "yaba", "agege", "mushin", "apapa", "festac",
                      "ojota", "maryland", "ketu", "ajah", "third mainland",
                      # Major Lagos roads — Lagos Traffic Radio uses these names
                      "ikorodu road", "lagos-ibadan expressway", "carter bridge",
                      "apapa-oshodi expressway", "lekki-epe expressway",
                      "oba akran", "airport road", "isale eko", "mile 2",
                      "oba ogunji", "ijaye", "agege motor road", "dolphin estate",
                      "lekki conservation", "jakande", "obalende", "cms",
                      "lastma", "lasg", "lspwc"],
    "nairobi":       ["nairobi", "westlands", "cbd", "thika", "langata", "karen",
                      "kasarani", "embakasi", "eastleigh", "mathare", "kibera",
                      "uthiru", "kikuyu", "waiyaki", "ngong road", "mombasa road"],
    "abuja":         ["abuja", "fct", "maitama", "wuse", "garki", "asokoro", "gwarinpa"],
    "kano":          ["kano"],
    "ibadan":        ["ibadan", "oyo"],
    "port harcourt": ["port harcourt", "portharcourt", "rivers"],
    "mombasa":       ["mombasa", "kilifi", "malindi"],
}

# Active RSS feeds for Nigeria and Kenya
RSS_FEEDS = {
    "nigeria": [
        # General Nigerian news
        "https://channelstv.com/feed",
        "https://pmnewsnigeria.com/feed",
        "https://vanguardngr.com/feed",
        "https://dailypost.ng/feed",
        # Lagos Traffic Radio (LASTMA) — official government traffic updates
        # Posts road-level flash updates every 10 min from live motorbike reporters
        "https://trafficradio961.ng/feed",
        "https://trafficradio961.ng/category/news/traffic-updates/feed",
        # FRSC National Traffic Radio Abuja — try feed, falls back silently if unavailable
        "https://frsc.gov.ng/feed",
    ],
    "kenya": [
        "https://kenyanews.go.ke/feed",
        "https://kenyans.co.ke/feeds/news",
        "https://nairobiwire.com/feed",
        "https://www.standardmedia.co.ke/rss",
        # Nation Africa — Kenya's largest daily, strong Nairobi traffic coverage
        "https://nation.africa/kenya/rss.xml",
    ]
}


# ═══════════════════════════════════════════════════════════════
# 1. TOMTOM TRAFFIC FLOW — real measured congestion
# ═══════════════════════════════════════════════════════════════

async def get_live_congestion(lat: float, lng: float, city: str) -> dict:
    """
    Get REAL measured traffic flow from TomTom.
    Returns congestion level and live speed vs free-flow speed.

    Free tier: 2,500 requests/day — enough for CommuteIQ.
    No credit card needed. Sign up: developer.tomtom.com

    Falls back to time-based estimate if key not set or API fails.
    """
    if not TOMTOM_API_KEY:
        return _time_based_congestion()

    cache_key = f"flow|{round(lat,2)}|{round(lng,2)}"
    if cache_key in _congestion_cache:
        entry = _congestion_cache[cache_key]
        if time.time() - entry["ts"] < CACHE_TTL:
            return entry["data"]

    try:
        # TomTom Traffic Flow API — point query
        url = (
            f"https://api.tomtom.com/traffic/services/4/flowSegmentData/"
            f"absolute/10/json"
            f"?key={TOMTOM_API_KEY}"
            f"&point={lat},{lng}"
            f"&unit=KMPH"
        )
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(url)
            if r.status_code != 200:
                return _time_based_congestion()
            data = r.json()

        flow = data.get("flowSegmentData", {})
        current_speed  = flow.get("currentSpeed",    0)
        free_flow_speed= flow.get("freeFlowSpeed",   1)
        confidence     = flow.get("confidence",      0)

        if free_flow_speed == 0:
            return _time_based_congestion()

        # Flow ratio: 1.0 = free flow, 0.5 = half speed, 0.2 = standstill
        ratio = current_speed / free_flow_speed

        if ratio >= 0.85:
            level = "Low"
        elif ratio >= 0.55:
            level = "Medium"
        else:
            level = "High"

        result = {
            "congestion":      level,
            "current_speed":   round(current_speed),
            "free_flow_speed": round(free_flow_speed),
            "flow_ratio":      round(ratio, 2),
            "confidence":      confidence,
            "source":          "TomTom live traffic",
            "live":            True,
        }
        _congestion_cache[cache_key] = {"data": result, "ts": time.time()}
        return result

    except Exception:
        return _time_based_congestion()


async def get_live_incidents(city: str) -> list:
    """
    Get real-time traffic incidents from TomTom for a city bounding box.
    Returns list of incidents with type, location, and severity.
    """
    if not TOMTOM_API_KEY or city.lower() not in CITY_BBOXES:
        return []

    cache_key = f"incidents|{city}"
    if cache_key in _congestion_cache:
        entry = _congestion_cache[cache_key]
        if time.time() - entry["ts"] < CACHE_TTL:
            return entry["data"]

    try:
        bbox = CITY_BBOXES[city.lower()]
        url  = (
            f"https://api.tomtom.com/traffic/services/5/incidentDetails"
            f"?key={TOMTOM_API_KEY}"
            f"&bbox={bbox}"
            f"&fields={{incidents{{type,geometry,properties{{id,iconCategory,magnitudeOfDelay,events,startTime,endTime,from,to,length,delay,roadNumbers,timeValidity}}}}}}"
            f"&language=en-GB"
            f"&t=1111&categoryFilter=0,1,2,3,4,5,6,7,8,9,10,11,14"
            f"&timeValidityFilter=present"
        )
        async with httpx.AsyncClient(timeout=8) as client:
            r = await client.get(url)
            if r.status_code != 200:
                return []
            data = r.json()

        incidents = []
        icon_to_type = {
            1: "accident",  2: "heavy_traffic", 3: "road_closure",
            4: "construction", 5: "flood", 6: "heavy_traffic",
            7: "heavy_traffic", 8: "construction", 9: "road_closure",
            10: "breakdown", 11: "heavy_traffic", 14: "heavy_traffic",
        }

        for inc in data.get("incidents", []):
            props = inc.get("properties", {})
            icon  = props.get("iconCategory", 0)
            delay = props.get("magnitudeOfDelay", 0)   # 0-4, 4=major
            events = props.get("events", [])
            location_from = props.get("from", "")
            location_to   = props.get("to", "")
            location = f"{location_from} → {location_to}" if location_from else city

            incidents.append({
                "type":     icon_to_type.get(icon, "heavy_traffic"),
                "location": location,
                "severity": delay,
                "source":   "TomTom live incidents",
                "live":     True,
                "created_at": time.time(),
                "expires_at": time.time() + 3600,
            })

        _congestion_cache[cache_key] = {"data": incidents, "ts": time.time()}
        return incidents

    except Exception:
        return []


# ═══════════════════════════════════════════════════════════════
# 2. RSS NEWS SCANNER — auto-generates incident reports from news
# ═══════════════════════════════════════════════════════════════

async def get_news_incidents(cities: list = None) -> list:
    """
    Scan Nigerian and Kenyan RSS feeds for traffic-related headlines.
    Converts news items into CommuteIQ community report format.

    Runs every 15 min (cached) — zero API cost.
    """
    global _last_news_scan

    # Cache for 15 minutes
    if time.time() - _last_news_scan < 900 and _news_cache:
        filtered = []
        for city in (cities or list(CITY_KEYWORDS.keys())):
            filtered.extend(_news_cache.get(city.lower(), []))
        return filtered

    all_incidents = {city: [] for city in CITY_KEYWORDS}
    feeds_to_scan = []

    # Determine which feeds to scan
    if cities:
        countries = set()
        for city in cities:
            if city.lower() in ["lagos","abuja","kano","ibadan","port harcourt","enugu"]:
                countries.add("nigeria")
            else:
                countries.add("kenya")
        for country in countries:
            feeds_to_scan.extend(RSS_FEEDS.get(country, []))
    else:
        for feeds in RSS_FEEDS.values():
            feeds_to_scan.extend(feeds)

    # Also add Google News targeted search
    google_queries = [
        "Lagos traffic accident today",
        "Lagos flood road closed",
        "Nairobi traffic accident today",
        "Nairobi flood Mombasa road",
    ]
    for q in google_queries:
        feeds_to_scan.append(
            f"https://news.google.com/rss/search?q={q.replace(' ','+')}+Africa&hl=en&gl=NG&ceid=NG:en"
        )

    async def fetch_feed(url: str) -> list:
        try:
            async with httpx.AsyncClient(
                timeout=8,
                headers={"User-Agent": "CommuteIQ/2.0 RSS scanner"}
            ) as client:
                r = await client.get(url, follow_redirects=True)
                if r.status_code != 200:
                    return []

            root    = ET.fromstring(r.text)
            channel = root.find("channel")
            if channel is None:
                return []

            items = []
            for item in channel.findall("item")[:20]:   # latest 20 articles
                title = item.findtext("title", "").lower()
                desc  = item.findtext("description", "").lower()
                link  = item.findtext("link", "")
                pub   = item.findtext("pubDate", "")
                text  = f"{title} {desc}"
                items.append({"title": title, "desc": desc, "link": link,
                              "pub": pub, "text": text})
            return items
        except Exception:
            return []

    # Fetch all feeds concurrently
    results = await asyncio.gather(*[fetch_feed(url) for url in feeds_to_scan])
    all_items = [item for batch in results for item in batch]

    # Parse items into incidents
    for item in all_items:
        text = item["text"]

        # Determine incident type
        incident_type = None
        for itype, keywords in INCIDENT_KEYWORDS.items():
            if any(kw in text for kw in keywords):
                incident_type = itype
                break
        if not incident_type:
            continue

        # Determine city
        incident_city = None
        for city, keywords in CITY_KEYWORDS.items():
            if any(kw in text for kw in keywords):
                incident_city = city
                break
        if not incident_city:
            continue

        # Build location string from title
        location = item["title"].replace("traffic", "").replace("accident", "").strip()
        location = location[:80] if len(location) > 80 else location

        incident = {
            "type":       incident_type,
            "location":   location or incident_city,
            "city":       incident_city,
            "source":     "news_scan",
            "source_url": item["link"],
            "confidence": 0.6,   # lower than community reports — news is less specific
            "lat":        None,
            "lng":        None,
            "created_at": time.time(),
            "expires_at": time.time() + (7200 if incident_type == "accident"
                          else 1200 if incident_type == "heavy_traffic"
                          else 86400),
        }
        all_incidents[incident_city].append(incident)

    # Update cache
    _news_cache.update(all_incidents)
    _last_news_scan = time.time()

    # Return for requested cities
    out = []
    for city in (cities or list(all_incidents.keys())):
        out.extend(all_incidents.get(city.lower(), []))

    # Deduplicate by type+city
    seen = set()
    deduped = []
    for inc in out:
        key = f"{inc['type']}|{inc['city']}"
        if key not in seen:
            seen.add(key)
            deduped.append(inc)

    return deduped


# ═══════════════════════════════════════════════════════════════
# 3. GOOGLE NEWS TARGETED SEARCH — on-demand incident lookup
# ═══════════════════════════════════════════════════════════════

async def search_news_for_route(origin: str, destination: str, city: str) -> list:
    """
    Search Google News RSS for incidents specifically on this route.
    Called when a prediction is made — looks for news about the specific
    origin/destination area in the last 24 hours.

    Completely free — Google News RSS requires no key.
    """
    queries = [
        f"{origin} {city} accident",
        f"{destination} {city} flood",
        f"{origin} {destination} road closed",
        f"{city} traffic {destination}",
    ]

    incidents = []
    for q in queries[:2]:   # limit to 2 searches per prediction
        url = f"https://news.google.com/rss/search?q={q.replace(' ','+')}+today&hl=en"
        try:
            async with httpx.AsyncClient(timeout=5, headers={"User-Agent": "CommuteIQ/2.0"}) as client:
                r = await client.get(url, follow_redirects=True)
                if r.status_code != 200:
                    continue

            root    = ET.fromstring(r.text)
            channel = root.find("channel")
            if not channel:
                continue

            for item in channel.findall("item")[:5]:
                title = item.findtext("title", "").lower()
                for itype, keywords in INCIDENT_KEYWORDS.items():
                    if any(kw in title for kw in keywords):
                        incidents.append({
                            "type":       itype,
                            "location":   f"{origin}–{destination} corridor",
                            "city":       city,
                            "source":     "google_news",
                            "source_url": item.findtext("link",""),
                            "confidence": 0.5,
                            "created_at": time.time(),
                            "expires_at": time.time() + 3600,
                        })
                        break
        except Exception:
            continue

        await asyncio.sleep(0.5)   # be polite to Google

    return incidents


# ═══════════════════════════════════════════════════════════════
# 4. OSM ROAD CLOSURES API — community-reported closures
# ═══════════════════════════════════════════════════════════════

# Bounding boxes used for OSM Overpass AND the closures.osm.ch API
OSM_CITY_BBOXES = {
    "lagos":         {"south": 6.38, "west": 3.10, "north": 6.71, "east": 3.72},
    "nairobi":       {"south": -1.44, "west": 36.65, "north": -1.16, "east": 37.01},
    "abuja":         {"south": 8.76, "west": 6.99, "north": 9.34, "east": 7.73},
    "kano":          {"south": 11.85, "west": 8.37, "north": 12.15, "east": 8.78},
    "ibadan":        {"south": 7.26, "west": 3.79, "north": 7.52, "east": 4.12},
    "port harcourt": {"south": 4.65, "west": 6.89, "north": 5.02, "east": 7.21},
    "mombasa":       {"south": -4.15, "west": 39.55, "north": -3.95, "east": 39.85},
    "nairobi":       {"south": -1.44, "west": 36.65, "north": -1.16, "east": 37.01},
}

_osm_cache: dict = {}


async def get_osm_road_closures(city: str) -> list:
    """
    Fetch community-reported road closures from OSM Road Closures API.
    New platform built in GSoC 2025 at closures.osm.ch — free, no API key.
    Returns closures with OpenLR location referencing for precise road matching.

    Falls back to Overpass API query for highway=construction if
    closures.osm.ch returns nothing.
    """
    cache_key = f"osm_closures|{city}"
    if cache_key in _osm_cache:
        entry = _osm_cache[cache_key]
        if time.time() - entry["ts"] < 900:   # 15 min cache
            return entry["data"]

    bbox = OSM_CITY_BBOXES.get(city.lower())
    if not bbox:
        return []

    incidents = []

    # ── Layer 1: OSM Road Closures API (closures.osm.ch) ─────
    try:
        url = (
            f"https://closures.osm.ch/api/closures"
            f"?bbox={bbox['west']},{bbox['south']},{bbox['east']},{bbox['north']}"
        )
        async with httpx.AsyncClient(timeout=8, headers={"User-Agent": "CommuteIQ/2.0"}) as client:
            r = await client.get(url)
            if r.status_code == 200:
                data = r.json()
                for closure in data.get("features", []):
                    props = closure.get("properties", {})
                    name  = props.get("name") or props.get("description") or city
                    start = props.get("start_date", "")
                    end   = props.get("end_date", "")
                    # Parse expiry
                    try:
                        from datetime import datetime as _dt
                        exp_ts = _dt.fromisoformat(end).timestamp() if end else time.time() + 86400
                    except Exception:
                        exp_ts = time.time() + 86400

                    incidents.append({
                        "type":       "road_closure",
                        "location":   name[:100],
                        "city":       city,
                        "source":     "osm_closures",
                        "confidence": 0.75,   # community-verified, higher than news
                        "created_at": time.time(),
                        "expires_at": exp_ts,
                    })
    except Exception:
        pass

    # ── Layer 2: Overpass API — highway=construction ──────────
    # Catches road works that OSM editors have tagged but aren't
    # in the closures API yet. Updated daily from OSM community edits.
    if len(incidents) < 3:   # only hit Overpass if closures API had little data
        try:
            overpass_query = f"""
[out:json][timeout:15];
(
  way["highway"="construction"]
     ({bbox['south']},{bbox['west']},{bbox['north']},{bbox['east']});
  way["construction"~"primary|secondary|tertiary|trunk|motorway"]
     ({bbox['south']},{bbox['west']},{bbox['north']},{bbox['east']});
  way["access"="no"]["highway"]
     ({bbox['south']},{bbox['west']},{bbox['north']},{bbox['east']});
);
out tags 10;
"""
            overpass_url = "https://overpass-api.de/api/interpreter"
            async with httpx.AsyncClient(timeout=12, headers={"User-Agent": "CommuteIQ/2.0"}) as client:
                r = await client.post(overpass_url, data={"data": overpass_query})
                if r.status_code == 200:
                    elements = r.json().get("elements", [])
                    for el in elements[:5]:   # cap at 5 to avoid noise
                        tags = el.get("tags", {})
                        name = (tags.get("name") or
                                tags.get("ref") or
                                tags.get("description") or
                                f"{city} road works")
                        incidents.append({
                            "type":       "construction",
                            "location":   name[:100],
                            "city":       city,
                            "source":     "osm_overpass",
                            "confidence": 0.65,
                            "created_at": time.time(),
                            "expires_at": time.time() + 86400,  # 24h — construction is slow-changing
                        })
        except Exception:
            pass

    _osm_cache[cache_key] = {"data": incidents, "ts": time.time()}
    return incidents


# ═══════════════════════════════════════════════════════════════
# HELPER — fallback to time-based congestion when no TomTom key
# ═══════════════════════════════════════════════════════════════

def _time_based_congestion() -> dict:
    """Original time-of-day estimate — used when TomTom key not set."""
    import datetime
    hour = datetime.datetime.now().hour
    if 7 <= hour <= 9 or 17 <= hour <= 19:
        level = "High"
    elif 10 <= hour <= 16 or 20 <= hour <= 21:
        level = "Medium"
    else:
        level = "Low"
    return {
        "congestion": level,
        "source":     "time_of_day_estimate",
        "live":       False,
    }


# ═══════════════════════════════════════════════════════════════
# COMBINED INTELLIGENCE — single call for main.py
# ═══════════════════════════════════════════════════════════════

async def get_route_intelligence(
    origin:      str,
    destination: str,
    city:        str,
    lat:         float,
    lng:         float,
) -> dict:
    """
    Single entry point for main.py to get all live intelligence.

    Returns:
    - congestion: level + live speed if TomTom available
    - incidents: combined from TomTom + RSS news + Google News
    - confidence_boost: extra confidence if data is live (not estimated)
    """
    # Run all four sources concurrently — fail safe on each
    congestion_result, tomtom_incidents, news_incidents, route_news, osm_closures = await asyncio.gather(
        get_live_congestion(lat, lng, city),
        get_live_incidents(city),
        get_news_incidents([city]),
        search_news_for_route(origin, destination, city),
        get_osm_road_closures(city),
        return_exceptions=True
    )

    # Handle exceptions gracefully — one source failing never breaks the others
    if isinstance(congestion_result, Exception):
        congestion_result = _time_based_congestion()
    if isinstance(tomtom_incidents, Exception):
        tomtom_incidents = []
    if isinstance(news_incidents, Exception):
        news_incidents = []
    if isinstance(route_news, Exception):
        route_news = []
    if isinstance(osm_closures, Exception):
        osm_closures = []

    # Combine all incident sources
    all_incidents = []
    for inc in (tomtom_incidents + news_incidents + route_news + osm_closures):
        if isinstance(inc, dict):
            all_incidents.append(inc)

    # Remove expired
    now = time.time()
    active_incidents = [i for i in all_incidents if i.get("expires_at", now+1) > now]

    # Confidence boost: live data is more trustworthy than guesses
    confidence_boost = 15 if congestion_result.get("live") else 0
    confidence_boost += min(len(active_incidents) * 5, 20)

    return {
        "congestion":        congestion_result["congestion"],
        "congestion_detail": congestion_result,
        "incidents":         active_incidents,
        "incident_count":    len(active_incidents),
        "confidence_boost":  confidence_boost,
        "data_sources":      list(set(
            [congestion_result.get("source", "time_estimate")] +
            [i.get("source", "unknown") for i in active_incidents]
        )),
    }
