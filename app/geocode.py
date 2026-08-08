"""Free geocoding via OpenStreetMap Nominatim — no API key needed.
Used by main.py's geocode_place() for resolving origin/destination.
Usage policy: max ~1 req/sec, descriptive User-Agent required.
"""
import httpx

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

# All supported cities mapped to their country code.
# Scoping to a country prevents "Westlands" resolving to Germany etc.
COUNTRY_CODE = {
    # Kenya
    "nairobi": "ke", "mombasa": "ke", "kisumu": "ke",
    "nakuru":  "ke", "eldoret": "ke", "kiambu": "ke",
    "machakos":"ke", "murang'a":"ke", "kilifi": "ke",
    "meru":    "ke", "nyeri":   "ke", "kajiado":"ke",
    "kirinyaga":"ke","narok":   "ke", "embu":   "ke",
    "kisii":   "ke", "homa bay":"ke", "kericho":"ke",
    "nyandarua":"ke","kakamega":"ke", "makueni":"ke",
    # Nigeria
    "lagos":         "ng", "abuja":        "ng",
    "kano":          "ng", "ibadan":       "ng",
    "port harcourt": "ng", "enugu":        "ng",
}

# City-centre fallback — returned when Nominatim finds nothing
CITY_CENTRES = {
    "nairobi":        {"lat": -1.2921,  "lng": 36.8219},
    "mombasa":        {"lat": -4.0435,  "lng": 39.6682},
    "kisumu":         {"lat": -0.0917,  "lng": 34.7680},
    "nakuru":         {"lat": -0.3031,  "lng": 36.0800},
    "eldoret":        {"lat":  0.5143,  "lng": 35.2698},
    "lagos":          {"lat":  6.5244,  "lng":  3.3792},
    "abuja":          {"lat":  9.0765,  "lng":  7.3986},
    "kano":           {"lat": 12.0022,  "lng":  8.5920},
    "ibadan":         {"lat":  7.3775,  "lng":  3.9470},
    "port harcourt":  {"lat":  4.8156,  "lng":  7.0498},
    "enugu":          {"lat":  6.4584,  "lng":  7.5464},
}

HEADERS = {"User-Agent": "CommuteIQ/1.0 (hackathon project)"}


async def geocode_location(query: str, city: str) -> dict:
    city_lower   = (city or "").lower()
    countrycodes = COUNTRY_CODE.get(city_lower, "")

    # Enrich query with city name to avoid global ambiguity
    q = query.strip()
    if city and city_lower not in q.lower():
        q = f"{q}, {city}"

    params = {"format": "json", "limit": 1, "q": q}
    if countrycodes:
        params["countrycodes"] = countrycodes

    async with httpx.AsyncClient(timeout=10) as client:
        res = await client.get(NOMINATIM_URL, params=params, headers=HEADERS)
        res.raise_for_status()
        results = res.json()

    if not results:
        # Return city centre instead of crashing — better UX
        fallback = CITY_CENTRES.get(city_lower, {"lat": -1.2921, "lng": 36.8219})
        return {**fallback, "label": city or "Unknown", "is_fallback": True}

    top = results[0]
    return {
        "lat":   float(top["lat"]),
        "lng":   float(top["lon"]),
        "label": top["display_name"],
    }
