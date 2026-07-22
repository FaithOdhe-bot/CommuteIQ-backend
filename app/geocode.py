"""Free geocoding via OpenStreetMap's Nominatim — no API key needed.
Usage policy: max ~1 request/sec, and a descriptive User-Agent is required.
Fine for a hackathon demo; self-host Nominatim or use a paid geocoder
if this needs to scale past prototype traffic.

Biased by COUNTRY CODE, not by a specific city — Nominatim already covers
every county/state in Kenya and Nigeria, so any location within the
selected country resolves correctly, not just Nairobi/Lagos.
"""
import httpx

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

COUNTRY_CODE = {
    "nairobi": "ke",
    "lagos": "ng",
}

HEADERS = {"User-Agent": "CommuteIQ-Hackathon/1.0 (student project)"}


async def geocode_location(query: str, city: str) -> dict:
    countrycodes = COUNTRY_CODE.get(city, "")
    params = {"format": "json", "limit": 1, "q": query}
    if countrycodes:
        params["countrycodes"] = countrycodes

    async with httpx.AsyncClient(timeout=10) as client:
        res = await client.get(NOMINATIM_URL, params=params, headers=HEADERS)
        res.raise_for_status()
        results = res.json()

    if not results:
        raise ValueError(f'Could not find a location for "{query}"')

    top = results[0]
    return {
        "lat": float(top["lat"]),
        "lng": float(top["lon"]),
        "label": top["display_name"],
    }