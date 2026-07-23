"""
CommuteIQ — Weather Intelligence Module
weather_intelligence.py

Features:
  1. Weather trend prediction — is rain coming in the next 30-60 min?
  2. Flood risk zones — Lagos and Nairobi known flood-prone areas
  3. Weather-aware departure window
"""

import time
from typing import Optional
from datetime import datetime, timezone


# ── WMO weather code → label ──────────────────────────────────
def wmo_to_label(code: int) -> str:
    if code in [51,53,55,61,63,65,80,81,82]: return "Rainy"
    elif code in [71,73,75,77,85,86]:         return "Snowy"
    elif code in [45,48]:                      return "Foggy"
    elif code in [1,2,3]:                      return "Cloudy"
    else:                                      return "Clear"

def is_bad_weather(label: str) -> bool:
    return label in ["Rainy", "Foggy", "Snowy"]


# ── Flood risk zones ──────────────────────────────────────────
# Known flood-prone areas based on local knowledge + OSM data
# Stored as (lat_min, lat_max, lng_min, lng_max, name, risk_level)

FLOOD_ZONES = {
    "lagos": [
        # Lekki-Ajah corridor — low-lying, frequently floods
        (6.43, 6.47, 3.48, 3.60, "Lekki-Ajah Expressway", "High"),
        # Mile 2 / Orile area
        (6.45, 6.48, 3.31, 3.35, "Mile 2 / Orile", "High"),
        # Oshodi underpass area
        (6.54, 6.56, 3.34, 3.36, "Oshodi Underpass", "High"),
        # Festac — drainage issues
        (6.45, 6.48, 3.27, 3.30, "Festac Town", "Medium"),
        # Marina / Lagos Island waterfront
        (6.44, 6.46, 3.38, 3.42, "Lagos Island Marina", "Medium"),
        # Ikorodu Road — floods at underpasses
        (6.56, 6.60, 3.36, 3.40, "Ikorodu Road", "Medium"),
        # Ojota / Ketu area
        (6.58, 6.62, 3.37, 3.41, "Ojota-Ketu", "Medium"),
    ],
    "nairobi": [
        # Mathare Valley — alongside Mathare River
        (-1.255, -1.245, 36.845, 36.865, "Mathare Valley", "High"),
        # Nairobi River basin — CBD area
        (-1.295, -1.280, 36.815, 36.835, "Nairobi River CBD", "High"),
        # Kibera — low-lying informal settlement
        (-1.318, -1.305, 36.778, 36.795, "Kibera", "High"),
        # Westlands along Nairobi River
        (-1.272, -1.260, 36.800, 36.815, "Westlands Riverside", "Medium"),
        # South B / South C drainage
        (-1.310, -1.295, 36.830, 36.850, "South B / South C", "Medium"),
        # Ngong Road dips
        (-1.308, -1.295, 36.760, 36.785, "Ngong Road Lowlands", "Medium"),
    ],
    "abuja": [
        (-8.90, -8.85, 7.35, 7.45, "Wuse Drainage Areas", "Medium"),
        (-9.05, -9.00, 7.40, 7.50, "Garki Lowlands", "Low"),
    ],
    "kano": [
        (11.99, 12.03, 8.49, 8.55, "Kano City Drainage", "Medium"),
    ],
}

# Day-of-week congestion multipliers
# Based on Nairobi OD data time slot patterns + Lagos research
DAY_CONGESTION_MULT = {
    0: 1.20,  # Monday — worst (everyone back from weekend)
    1: 1.10,  # Tuesday
    2: 1.00,  # Wednesday — baseline
    3: 1.05,  # Thursday
    4: 1.15,  # Friday — early rush
    5: 0.60,  # Saturday
    6: 0.40,  # Sunday
}

DAY_NAMES = {
    0: "Monday", 1: "Tuesday", 2: "Wednesday",
    3: "Thursday", 4: "Friday", 5: "Saturday", 6: "Sunday"
}


def get_flood_risk(city: str, origin_coords: dict, dest_coords: dict, weather: str) -> dict:
    """
    Check if a route passes through known flood-prone areas.
    Cross-references weather with flood zone geography.
    Returns risk assessment and affected zones.
    """
    city_zones = FLOOD_ZONES.get(city.lower(), [])
    if not city_zones or not is_bad_weather(weather):
        return {"risk": "Low", "zones": [], "warning": None}

    affected = []

    # Check if origin or destination is in a flood zone
    all_coords = [origin_coords, dest_coords]
    for coords in all_coords:
        lat = coords.get("lat", 0)
        lng = coords.get("lng", 0)
        for (lat_min, lat_max, lng_min, lng_max, name, risk) in city_zones:
            if lat_min <= lat <= lat_max and lng_min <= lng <= lng_max:
                if name not in [z["name"] for z in affected]:
                    affected.append({"name": name, "risk": risk})

    # Also check route corridor (simplified — midpoint check)
    if origin_coords and dest_coords:
        mid_lat = (origin_coords.get("lat",0) + dest_coords.get("lat",0)) / 2
        mid_lng = (origin_coords.get("lng",0) + dest_coords.get("lng",0)) / 2
        for (lat_min, lat_max, lng_min, lng_max, name, risk) in city_zones:
            if lat_min <= mid_lat <= lat_max and lng_min <= mid_lng <= lng_max:
                if name not in [z["name"] for z in affected]:
                    affected.append({"name": name, "risk": risk})

    if not affected:
        # Even without direct zone hit, warn about city-wide flood risk in rain
        if weather == "Rainy" and city.lower() in ["lagos", "nairobi"]:
            return {
                "risk":    "Medium",
                "zones":   [],
                "warning": f"⚠️ Rain detected in {city.title()} — low-lying roads may flood. Check local reports before travelling.",
            }
        return {"risk": "Low", "zones": [], "warning": None}

    # Determine overall risk
    has_high = any(z["risk"] == "High" for z in affected)
    overall  = "High" if has_high else "Medium"
    zone_names = ", ".join(z["name"] for z in affected)

    return {
        "risk":    overall,
        "zones":   affected,
        "warning": (
            f"🚨 Flood risk {'CRITICAL' if has_high else 'WARNING'}: "
            f"Your route passes through {zone_names}. "
            f"{'Avoid this route — seek an alternative.' if has_high else 'Proceed with caution — roads may be waterlogged.'}"
        ),
    }


async def get_weather_trend(lat: float, lng: float, httpx_client=None) -> dict:
    """
    Fetch hourly weather forecast and detect if rain is coming.
    Returns current weather + trend for next 1-3 hours.

    Uses Open-Meteo free API — no key required.
    """
    import httpx

    try:
        async with httpx.AsyncClient(timeout=6) as client:
            r = await client.get(
                "https://api.open-meteo.com/v1/forecast",
                params={
                    "latitude":        lat,
                    "longitude":       lng,
                    "current_weather": True,
                    "hourly":          "precipitation,weathercode,windspeed_10m",
                    "forecast_days":   1,
                    "timezone":        "auto",
                }
            )
            data = r.json()

        current     = data.get("current_weather", {})
        hourly      = data.get("hourly", {})
        times       = hourly.get("time", [])
        precip      = hourly.get("precipitation", [])
        codes       = hourly.get("weathercode", [])

        # Find current hour index
        now_str  = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:00")
        try:
            curr_idx = times.index(now_str)
        except ValueError:
            curr_idx = 0

        # Get next 3 hours
        next_hours = []
        for i in range(1, 4):
            idx = curr_idx + i
            if idx < len(times):
                next_hours.append({
                    "time":        times[idx],
                    "hour_offset": i,
                    "label":       wmo_to_label(codes[idx]) if idx < len(codes) else "Clear",
                    "precipitation": precip[idx] if idx < len(precip) else 0,
                    "weathercode": codes[idx] if idx < len(codes) else 0,
                })

        # Current
        curr_code  = current.get("weathercode", 0)
        curr_label = wmo_to_label(curr_code)
        curr_wind  = current.get("windspeed", 0)

        # Trend analysis
        rain_coming   = any(is_bad_weather(h["label"]) for h in next_hours[:2])
        clearing_soon = curr_label in ["Rainy","Foggy"] and all(
            not is_bad_weather(h["label"]) for h in next_hours[1:]
        )
        rain_in_hours = next(
            (h["hour_offset"] for h in next_hours if is_bad_weather(h["label"])),
            None
        )

        # Generate trend message
        if rain_coming and curr_label == "Clear":
            trend_msg  = f"⚠️ Rain expected in ~{rain_in_hours} hour{'s' if rain_in_hours > 1 else ''} — leave now or wait it out."
            trend_type = "rain_incoming"
        elif clearing_soon:
            trend_msg  = "🌤️ Current rain clearing soon — waiting 30-60 min could improve conditions significantly."
            trend_type = "clearing"
        elif is_bad_weather(curr_label) and rain_coming:
            trend_msg  = "🌧️ Rain continuing for the next 2+ hours — plan accordingly."
            trend_type = "persistent_rain"
        else:
            trend_msg  = "✅ Weather stable for the next 3 hours."
            trend_type = "stable"

        return {
            "current":       {"label": curr_label, "code": curr_code, "wind_kmh": curr_wind},
            "next_3_hours":  next_hours,
            "rain_coming":   rain_coming,
            "clearing_soon": clearing_soon,
            "trend_type":    trend_type,
            "trend_message": trend_msg,
            "source":        "Open-Meteo live forecast",
        }

    except Exception as e:
        # Graceful fallback
        return {
            "current":       {"label": "Clear", "code": 0, "wind_kmh": 0},
            "next_3_hours":  [],
            "rain_coming":   False,
            "clearing_soon": False,
            "trend_type":    "unknown",
            "trend_message": "Weather forecast unavailable — using current conditions only.",
            "source":        "fallback",
        }


def get_day_pattern(city: str, time_str: Optional[str] = None) -> dict:
    """
    Return day-of-week congestion pattern.
    Monday is always worse. Sunday is always better.
    Based on historical OD matrix patterns.
    """
    day_num  = datetime.now().weekday()
    day_name = DAY_NAMES[day_num]
    mult     = DAY_CONGESTION_MULT[day_num]

    # Context message
    if mult >= 1.15:
        pattern_msg = f"📅 {day_name} is historically one of the busiest commute days — allow extra time."
        severity    = "High"
    elif mult >= 1.05:
        pattern_msg = f"📅 {day_name} is slightly busier than average."
        severity    = "Medium"
    elif mult <= 0.60:
        pattern_msg = f"📅 {day_name} — light traffic expected. Great day to commute."
        severity    = "Low"
    else:
        pattern_msg = f"📅 {day_name} — typical traffic patterns expected."
        severity    = "Normal"

    return {
        "day":              day_name,
        "day_num":          day_num,
        "congestion_mult":  mult,
        "severity":         severity,
        "pattern_message":  pattern_msg,
    }
