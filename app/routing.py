"""Real routing on actual OpenStreetMap road data via the free public OSRM
demo server — genuine driving/walking distance and duration, no invented
numbers. The public demo server is rate-limited and meant for light/
prototype use; self-host OSRM or use a paid router for production traffic.
"""
import httpx

OSRM_URL = "https://router.project-osrm.org/route/v1"

# OSRM only has routing profiles for driving, walking, and cycling.
# There is no matatu/danfo/okada profile because informal transit is not
# mapped as a routable network anywhere. We use the driving profile as the
# physical-road baseline for all motorised modes, then apply mode-specific
# speed multipliers from transport_modes.pkl (see main.py _formula_travel_time).
OSRM_PROFILE = {
    # Nigeria modes
    "driving":   "driving",
    "danfo":     "driving",
    "brt":       "driving",   # dedicated lane but still on roads
    "okada":     "driving",
    "keke":      "driving",
    "rideshare": "driving",
    "walking":   "foot",
    # Kenya modes
    "matatu":    "driving",
    "bus":       "driving",
    "boda_boda": "driving",
    "boda":      "driving",   # alias
    "tuk_tuk":   "driving",
    "taxi":      "driving",
}


async def get_route(origin: dict, destination: dict, mode: str) -> dict:
    profile = OSRM_PROFILE.get(mode.lower(), "driving")
    coords  = f"{origin['lng']},{origin['lat']};{destination['lng']},{destination['lat']}"
    url     = f"{OSRM_URL}/{profile}/{coords}"

    async with httpx.AsyncClient(timeout=10) as client:
        res = await client.get(url, params={"overview": "false"})
        res.raise_for_status()
        data = res.json()

    if data.get("code") != "Ok" or not data.get("routes"):
        raise ValueError("No route found between those points")

    route = data["routes"][0]
    return {
        "distance_km":          route["distance"] / 1000,
        "base_duration_minutes": route["duration"] / 60,  # free-flow, congestion applied in main.py
    }
