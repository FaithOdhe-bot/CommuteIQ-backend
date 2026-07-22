"""Real routing on actual OpenStreetMap road data via the free public OSRM
demo server — genuine driving/walking distance and duration, no invented
numbers. The public demo server is rate-limited and meant for light/
prototype use; self-host OSRM or use a paid router for production traffic.
"""
import httpx

OSRM_URL = "https://router.project-osrm.org/route/v1"

# OSRM only has routing profiles for driving, walking, and cycling — there's
# no "matatu" or "danfo" profile because informal transit isn't mapped as a
# routable network anywhere. We use the driving profile as the physical-road
# baseline, then apply a documented multiplier (see congestion.py) to
# approximate those modes.
OSRM_PROFILE = {
    "driving": "driving",
    "walking": "foot",
    "boda": "driving",
    "matatu": "driving",
    "danfo": "driving",
}


async def get_route(origin: dict, destination: dict, mode: str) -> dict:
    profile = OSRM_PROFILE.get(mode, "driving")
    coords = f"{origin['lng']},{origin['lat']};{destination['lng']},{destination['lat']}"
    url = f"{OSRM_URL}/{profile}/{coords}"

    async with httpx.AsyncClient(timeout=10) as client:
        res = await client.get(url, params={"overview": "false"})
        res.raise_for_status()
        data = res.json()

    if data.get("code") != "Ok" or not data.get("routes"):
        raise ValueError("No route found between those points")

    route = data["routes"][0]
    return {
        "distance_km": route["distance"] / 1000,
        "base_duration_minutes": route["duration"] / 60,  # free-flow time, no congestion yet
    }
