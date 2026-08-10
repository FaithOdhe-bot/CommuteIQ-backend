"""
CommuteIQ — Transit Hub & Matatu Route Database
transit_data.py

Contains:
1. Major matatu stages per Nairobi area with walking distances
2. Matatu route numbers for common suburb → CBD trips  
3. Walk-to-transit logic for when driving is stuck in traffic
"""

# ── Nairobi Matatu Routes ─────────────────────────────────────
# suburb_lower → {route_number, stage_name, via_road}
MATATU_ROUTES = {
    "nairobi": {
        "kingeero":        {"routes": ["105","118","103"], "via": "Lower Kabete Rd/Waiyaki Way",  "stage": "Kingeero Stage"},
        "king'eero":       {"routes": ["105","118","103"], "via": "Lower Kabete Rd/Waiyaki Way",  "stage": "Kingeero Stage"},
        "uthiru":          {"routes": ["105","118"],       "via": "Lower Kabete Road",            "stage": "Uthiru Stage"},
        "kikuyu":          {"routes": ["105"],             "via": "Waiyaki Way",                  "stage": "Kikuyu Town Stage"},
        "kasarani":        {"routes": ["102","44"],        "via": "Kasarani/Mwiki Road",           "stage": "Kasarani Stage"},
        "ngong":           {"routes": ["111"],             "via": "Ngong Road",                   "stage": "Ngong Town Stage"},
        "githurai":        {"routes": ["45"],              "via": "Thika Road",                   "stage": "Githurai 45 Stage"},
        "rongai":          {"routes": ["111","125"],       "via": "Lang'ata Road/Magadi Road",     "stage": "Rongai Stage"},
        "thika":           {"routes": ["237"],             "via": "Thika Superhighway",            "stage": "Thika Stage"},
        "kawangware":      {"routes": ["46","56"],         "via": "Kawangware Road",               "stage": "Kawangware Stage"},
        "westlands":       {"routes": ["20","23"],         "via": "Waiyaki Way",                  "stage": "Westlands Stage"},
        "karen":           {"routes": ["111"],             "via": "Ngong Road",                   "stage": "Karen Stage"},
        "langata":         {"routes": ["125"],             "via": "Lang'ata Road",                "stage": "Lang'ata Stage"},
        "embakasi":        {"routes": ["34"],              "via": "Mombasa Road",                 "stage": "Embakasi Stage"},
        "donholm":         {"routes": ["58"],              "via": "Outer Ring Road",              "stage": "Donholm Stage"},
        "eastleigh":       {"routes": ["10","11"],         "via": "Juja Road",                    "stage": "Eastleigh Stage"},
        "south b":         {"routes": ["33"],              "via": "Lang'ata Road",                "stage": "South B Stage"},
        "south c":         {"routes": ["33"],              "via": "Mombasa Road",                 "stage": "South C Stage"},
        "kitengela":       {"routes": ["125T"],            "via": "Mombasa Road/EPZ",             "stage": "Kitengela Stage"},
        "rongai":          {"routes": ["111","125"],       "via": "Langata/Magadi Road",          "stage": "Rongai Stage"},
        "ruiru":           {"routes": ["237"],             "via": "Thika Superhighway",            "stage": "Ruiru Stage"},
        "githurai":        {"routes": ["45"],              "via": "Thika Road",                   "stage": "Githurai Stage"},
    }
}

# ── Lagos BRT + Danfo Routes ──────────────────────────────────
TRANSIT_ROUTES = {
    "lagos": {
        "ikeja":           {"routes": ["BRT-L1"], "via": "Ikorodu Road/BRT corridor", "stage": "Ikeja Under Bridge"},
        "maryland":        {"routes": ["BRT-L1"], "via": "Ikorodu Road BRT",          "stage": "Maryland BRT"},
        "ojota":           {"routes": ["BRT-L1","A5"], "via": "Ikorodu Road",         "stage": "Ojota Terminal"},
        "ketu":            {"routes": ["BRT-L1"], "via": "Ikorodu Road BRT",          "stage": "Ketu BRT"},
        "ikorodu":         {"routes": ["BRT-L1"], "via": "Ikorodu Road BRT",          "stage": "Ikorodu Terminal"},
        "lekki":           {"routes": ["L4"],     "via": "Lekki-Epe Expressway",      "stage": "Lekki Phase 1 Bus Stop"},
        "ajah":            {"routes": ["L4"],     "via": "Lekki-Epe Expressway",      "stage": "Ajah Bus Stop"},
        "surulere":        {"routes": ["L2"],     "via": "Lagos-Badagry Expressway",  "stage": "Ojuelegba Bus Stop"},
        "yaba":            {"routes": ["L2","S1"], "via": "Herbert Macaulay Way",     "stage": "Yaba Bus Stop"},
    }
}

# ── Transit hubs with coordinates for walk-to suggestions ─────
TRANSIT_HUBS = {
    "nairobi": [
        {"name": "Fig Tree A Terminus",   "lat": -1.2750, "lng": 36.8103, "serves": ["waiyaki way","lower kabete","kingeero","uthiru","kikuyu","westlands"]},
        {"name": "Fig Tree B Terminus",   "lat": -1.2748, "lng": 36.8100, "serves": ["thika road","kasarani","ruiru","githurai","roysambu"]},
        {"name": "Muthurwa Terminus",     "lat": -1.2833, "lng": 36.8489, "serves": ["jogoo road","donholm","embakasi","south b"]},
        {"name": "Hakati Terminus",       "lat": -1.3100, "lng": 36.8253, "serves": ["mombasa road","south c","embakasi","athi river","kitengela"]},
        {"name": "Railways Terminus",     "lat": -1.2967, "lng": 36.8200, "serves": ["ngong road","karen","langata","rongai","kawangware"]},
        {"name": "Ngara Terminus",        "lat": -1.2764, "lng": 36.8339, "serves": ["juja road","eastleigh","mathare"]},
    ],
    "lagos": [
        {"name": "Ikeja BRT Terminal",    "lat": 6.5958,  "lng": 3.3416,  "serves": ["ikeja","maryland","ketu","ojota","ikorodu"]},
        {"name": "TBS (Lagos Island)",    "lat": 6.4513,  "lng": 3.3931,  "serves": ["all lagos island routes"]},
        {"name": "Ojuelegba Bus Stop",    "lat": 6.4996,  "lng": 3.3560,  "serves": ["surulere","yaba","lekki","vi"]},
    ],
}


def get_matatu_route(origin: str, city: str) -> dict | None:
    """Return matatu route info for a suburb → CBD trip."""
    city_routes = MATATU_ROUTES.get(city.lower(), {})
    return city_routes.get(origin.lower().strip())


def get_walk_to_transit(
    origin_lat: float,
    origin_lng: float,
    city: str,
    origin_name: str,
    travel_time_driving: float,
    congestion: str,
) -> dict | None:
    """
    When traffic is High and driving would be slow, suggest walking
    to the nearest transit hub and taking public transit instead.

    Returns suggestion if walk + transit time < driving time.
    """
    import math

    if congestion != "High":
        return None

    def dist_km(lat1, lng1, lat2, lng2):
        dlat = (lat2-lat1)*math.pi/180
        dlng = (lng2-lng1)*math.pi/180
        a = math.sin(dlat/2)**2 + math.cos(lat1*math.pi/180)*math.cos(lat2*math.pi/180)*math.sin(dlng/2)**2
        return 6371 * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

    hubs = TRANSIT_HUBS.get(city.lower(), [])
    if not hubs:
        return None

    # Find nearest hub within walking distance (< 2km)
    closest = None
    closest_dist = float("inf")
    for hub in hubs:
        d = dist_km(origin_lat, origin_lng, hub["lat"], hub["lng"])
        if d < closest_dist and d < 2.0:
            closest_dist = d
            closest = hub

    if not closest:
        return None

    # Estimate walk + transit time
    walk_speed_kmh = 4.5
    walk_min = round((closest_dist / walk_speed_kmh) * 60)

    # Matatu/bus from terminus: typically 30-50 min to CBD at peak
    transit_min = 40  # conservative peak estimate

    total_alt = walk_min + transit_min

    if total_alt >= travel_time_driving:
        return None  # driving is faster — no suggestion needed

    time_saved = round(travel_time_driving - total_alt)

    # Get matatu route info
    route_info = get_matatu_route(origin_name.lower(), city)
    route_str = ""
    if route_info:
        routes = "/".join(route_info["routes"])
        route_str = f" Take Matatu Route {routes} from {closest['name']}."

    return {
        "type":         "walk_to_transit",
        "hub_name":     closest["name"],
        "walk_min":     walk_min,
        "walk_dist_km": round(closest_dist, 2),
        "transit_min":  transit_min,
        "total_min":    total_alt,
        "time_saved":   time_saved,
        "route_info":   route_info,
        "suggestion": (
            f"🚶 Consider walking {walk_min} min ({closest_dist:.1f}km) to "
            f"{closest['name']}, then taking public transit to CBD — "
            f"estimated {total_alt} min total vs {round(travel_time_driving)} min "
            f"in current traffic. Saves ~{time_saved} min.{route_str}"
        ),
    }
