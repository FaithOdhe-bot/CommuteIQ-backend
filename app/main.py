"""
CommuteIQ — FastAPI Backend
main.py

Endpoints:
  POST /predict   → travel time, commute quality, safety score, AI explanation
  POST /recommend → departure time recommendation
  POST /report    → submit community report
  GET  /reports   → list community reports for a city
  GET  /health    → health check
"""

import os
import time
import joblib
import httpx
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ── Internal modules (already written by teammate) ──────────────────────────
from models import PredictRequest, ReportRequest
from routing import get_route
from storage import save_report, list_reports


# ── App setup ────────────────────────────────────────────────────────────────

app = FastAPI(
    title="CommuteIQ",
    description="Community-powered AI mobility assistant for African cities",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],    # tighten this in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Load ML models at startup ─────────────────────────────────────────────────

MODELS_DIR = Path(__file__).parent.parent / "models"

def load_models():
    """Load pkl files. Fail loudly so you know immediately if paths are wrong."""
    try:
        travel_model   = joblib.load(MODELS_DIR / "travel_time_model.pkl")
        safety_scores  = joblib.load(MODELS_DIR / "safety_scores.pkl")
        encoders       = joblib.load(MODELS_DIR / "encoders.pkl")
        print("✅ Models loaded successfully")
        return travel_model, safety_scores, encoders
    except FileNotFoundError as e:
        print(f"⚠️  Model file not found: {e}")
        print("   Run train_models.py first, then copy /models here.")
        return None, None, None

travel_model, safety_scores, encoders = load_models()


# ── Weather helper ────────────────────────────────────────────────────────────

WEATHER_API = "https://api.open-meteo.com/v1/forecast"

async def get_weather(lat: float, lng: float) -> dict:
    """
    Fetch current weather from Open-Meteo (free, no API key).
    Returns simplified weather dict. Falls back to defaults if offline.
    """
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(WEATHER_API, params={
                "latitude": lat,
                "longitude": lng,
                "current_weather": True,
                "hourly": "precipitation",
            })
            data = r.json()
            code = data.get("current_weather", {}).get("weathercode", 0)
            wind = data.get("current_weather", {}).get("windspeed", 0)

            # WMO weather codes → simplified label
            if code in [51, 53, 55, 61, 63, 65, 80, 81, 82]:
                label = "Rainy"
            elif code in [45, 48]:
                label = "Foggy"
            elif code in [1, 2, 3]:
                label = "Cloudy"
            else:
                label = "Clear"

            return {"label": label, "code": code, "wind_kmh": wind}
    except Exception:
        return {"label": "Clear", "code": 0, "wind_kmh": 0}


# ── ML inference helpers ──────────────────────────────────────────────────────

def encode_features(distance_km: float, congestion: str, weather: str, alternatives: int) -> list:
    """Convert raw inputs to model feature vector."""
    cmap = encoders["congestion_map"] if encoders else {"Low": 0, "Medium": 1, "High": 2}
    wmap = encoders["weather_map"]    if encoders else {"Clear": 0, "Cloudy": 1, "Foggy": 2, "Rainy": 3}

    congestion_enc = cmap.get(congestion, 1)
    weather_enc    = wmap.get(weather, 0)
    is_peak        = int(congestion_enc >= 1 and weather_enc >= 1)

    return [[distance_km, congestion_enc, weather_enc, alternatives, is_peak]]


def predict_travel_time(distance_km: float, congestion: str, weather: str, alternatives: int) -> float:
    """Predict travel time in minutes using ML model, or formula fallback."""
    if travel_model is None:
        # Fallback: base speed adjusted by congestion and weather
        speeds = {"Low": 60, "Medium": 40, "High": 20}
        multipliers = {"Clear": 1.0, "Cloudy": 1.05, "Foggy": 1.15, "Rainy": 1.25}
        speed = speeds.get(congestion, 40) * multipliers.get(weather, 1.0)
        return round((distance_km / speed) * 60, 1)

    features = encode_features(distance_km, congestion, weather, alternatives)
    return round(float(travel_model.predict(features)[0]), 1)


def get_commute_quality(congestion: str, weather: str, community_reports: int, safety_score: float) -> dict:
    """
    Rule-based commute quality — more reliable than ML for this dataset.
    Returns label, emoji, and score 0-100.

    Rules:
      🟢 Good     → low congestion, clear/cloudy, no reports
      🟡 Moderate → medium congestion OR bad weather OR 1-2 reports
      🔴 Poor     → high congestion OR rainy/foggy + reports OR 3+ reports
    """
    bad_weather  = weather in ["Rainy", "Foggy"]
    high_traffic = congestion == "High"
    low_safety   = safety_score < 50

    if high_traffic or (bad_weather and community_reports >= 1) or community_reports >= 3:
        return {"label": "Poor",     "emoji": "🔴", "score": 30}
    elif congestion == "Medium" or bad_weather or community_reports >= 1 or low_safety:
        return {"label": "Moderate", "emoji": "🟡", "score": 60}
    else:
        return {"label": "Good",     "emoji": "🟢", "score": 90}


def get_safety_score(city: str, mode: str) -> float:
    """Look up safety score from crash data. Falls back to city baseline."""
    if safety_scores is None:
        return 65.0

    # Mode risk multipliers (boda/okada riskier)
    mode_mult = {
        "driving":  1.00,
        "walking":  0.95,
        "danfo":    0.98,
        "matatu":   0.98,
        "boda":     0.80,
        "rideshare": 1.00,
    }

    base = safety_scores.get(city.lower(), safety_scores.get("default", 60.0))
    mult = mode_mult.get(mode.lower(), 1.0)
    return round(min(100, max(0, base * mult)), 1)


def generate_ai_explanation(
    origin: str,
    destination: str,
    travel_time: float,
    quality: dict,
    safety_score: float,
    weather: str,
    congestion: str,
    community_reports: int,
    departure_advice: str,
) -> str:
    """
    Generate a plain-language AI explanation.
    This is SmartCommute AI's key differentiator — no other African app does this.
    """
    lines = []

    # Opening: route summary
    lines.append(f"Route {origin} → {destination} estimated at {travel_time:.0f} min.")

    # Condition assessment
    if weather in ["Rainy", "Foggy"]:
        weather_note = f"{'Rain' if weather == 'Rainy' else 'Fog'} is currently affecting road visibility and speed."
        lines.append(weather_note)

    if congestion == "High":
        lines.append("Heavy traffic reported on this corridor.")
    elif congestion == "Medium":
        lines.append("Moderate congestion detected.")

    if community_reports > 0:
        lines.append(
            f"{community_reports} community report{'s' if community_reports > 1 else ''} "
            f"filed on this route in the last hour."
        )

    # Safety
    if safety_score >= 75:
        lines.append(f"Safety score {safety_score:.0f}/100 — this is a relatively safe corridor.")
    elif safety_score >= 50:
        lines.append(f"Safety score {safety_score:.0f}/100 — exercise normal caution.")
    else:
        lines.append(
            f"Safety score {safety_score:.0f}/100 — this corridor has elevated crash risk. "
            f"Drive carefully and stay alert."
        )

    # Quality verdict
    emoji = quality["emoji"]
    label = quality["label"]
    lines.append(f"Overall commute quality: {emoji} {label}.")

    # Departure advice
    if departure_advice != "Leave now":
        lines.append(departure_advice)

    return " ".join(lines)


def get_departure_advice(congestion: str, weather: str, travel_time: float) -> str:
    """
    Recommend when to leave based on current conditions.
    SmartCommute AI's core value proposition: 'when', not just 'where'.
    """
    if congestion == "High" and weather in ["Rainy", "Foggy"]:
        wait = 20
        saved = round(travel_time * 0.30)
        return f"Wait {wait} min — leaving later could save ~{saved} min on this route."
    elif congestion == "High":
        wait = 15
        saved = round(travel_time * 0.20)
        return f"Wait {wait} min — conditions may ease and save ~{saved} min."
    elif weather in ["Rainy", "Foggy"]:
        return "Leave now but allow extra time — weather is reducing speeds."
    else:
        return "Leave now — conditions are good."


# ── Request/Response models ───────────────────────────────────────────────────

class PredictResponse(BaseModel):
    travel_time_min:   float
    commute_quality:   str
    quality_emoji:     str
    quality_score:     int
    safety_score:      float
    weather:           str
    congestion:        str
    departure_advice:  str
    ai_explanation:    str
    distance_km:       Optional[float] = None
    community_reports: int = 0


class RecommendRequest(BaseModel):
    origin:      str
    destination: str
    mode:        str
    city:        str
    time:        Optional[str] = None


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "models_loaded": travel_model is not None,
        "safety_scores_loaded": safety_scores is not None,
    }


@app.post("/predict", response_model=PredictResponse)
async def predict(req: PredictRequest):
    """
    Main prediction endpoint.
    Accepts origin, destination, mode, city, time.
    Returns travel time, quality, safety score, and AI explanation.
    """

    # 1. Get real route from OSRM
    try:
        # Geocode origin and destination via Nominatim
        async with httpx.AsyncClient(timeout=8) as client:
            def geocode(place: str, city: str):
                return f"{place}, {city}"

            origin_coords = await geocode_place(req.origin, req.city)
            dest_coords   = await geocode_place(req.destination, req.city)

        route = await get_route(origin_coords, dest_coords, req.mode)
        distance_km = route["distance_km"]

    except Exception:
        # Fallback: use a reasonable distance estimate
        distance_km = 15.0

    # 2. Get weather
    # Default coords for cities (fallback when geocoding fails)
    city_coords = {
        "lagos":   {"lat": 6.5244, "lng": 3.3792},
        "nairobi": {"lat": -1.2921, "lng": 36.8219},
        "abuja":   {"lat": 9.0765, "lng": 7.3986},
        "kano":    {"lat": 12.0022, "lng": 8.5920},
    }
    coords = city_coords.get(req.city.lower(), {"lat": 6.5244, "lng": 3.3792})
    weather_data = await get_weather(coords["lat"], coords["lng"])
    weather = weather_data["label"]

    # 3. Estimate congestion from time of day
    congestion = estimate_congestion(req.time)

    # 4. Get community reports count for this route
    reports = await list_reports(req.city)
    community_count = len([
        r for r in reports
        if r.get("type") in ["accident", "flood", "road_closure", "heavy_traffic"]
        and (time.time() - r.get("created_at", 0)) < 3600  # last hour only
    ])

    # 5. ML predictions
    travel_time   = predict_travel_time(distance_km, congestion, weather, 2)
    safety_score  = get_safety_score(req.city, req.mode)
    quality       = get_commute_quality(congestion, weather, community_count, safety_score)

    # 6. Departure advice
    departure_advice = get_departure_advice(congestion, weather, travel_time)

    # 7. AI explanation
    ai_explanation = generate_ai_explanation(
        origin=req.origin,
        destination=req.destination,
        travel_time=travel_time,
        quality=quality,
        safety_score=safety_score,
        weather=weather,
        congestion=congestion,
        community_reports=community_count,
        departure_advice=departure_advice,
    )

    return PredictResponse(
        travel_time_min=travel_time,
        commute_quality=quality["label"],
        quality_emoji=quality["emoji"],
        quality_score=quality["score"],
        safety_score=safety_score,
        weather=weather,
        congestion=congestion,
        departure_advice=departure_advice,
        ai_explanation=ai_explanation,
        distance_km=round(distance_km, 2),
        community_reports=community_count,
    )


@app.post("/report")
async def submit_report(req: ReportRequest):
    """Submit a community road report (accident, flood, closure, traffic)."""
    report = {
        "city":       req.city,
        "type":       req.type,
        "location":   req.location,
        "lat":        req.lat,
        "lng":        req.lng,
        "timestamp":  time.time(),
        "created_at": time.time(),
    }
    result = await save_report(report)
    return {"ok": True, "message": "Report submitted. Thank you!", "storage": result.get("storage")}


@app.get("/reports")
async def get_reports(city: Optional[str] = None):
    """Get recent community reports, optionally filtered by city."""
    reports = await list_reports(city)
    # Only return reports from the last 6 hours
    cutoff = time.time() - (6 * 3600)
    recent = [r for r in reports if r.get("created_at", 0) > cutoff]
    return {"reports": recent, "count": len(recent)}


# ── Helper: geocode place name via Nominatim ──────────────────────────────────

async def geocode_place(place: str, city: str) -> dict:
    """Geocode a place name to lat/lng using OpenStreetMap Nominatim."""
    query = f"{place}, {city}"
    try:
        async with httpx.AsyncClient(
            timeout=6,
            headers={"User-Agent": "SmartCommuteAI/1.0"},
        ) as client:
            r = await client.get(
                "https://nominatim.openstreetmap.org/search",
                params={"q": query, "format": "json", "limit": 1},
            )
            results = r.json()
            if results:
                return {"lat": float(results[0]["lat"]), "lng": float(results[0]["lon"])}
    except Exception:
        pass

    # Fallback coords per city
    defaults = {
        "lagos":   {"lat": 6.5244, "lng": 3.3792},
        "nairobi": {"lat": -1.2921, "lng": 36.8219},
        "abuja":   {"lat": 9.0765, "lng": 7.3986},
    }
    return defaults.get(city.lower(), {"lat": 6.5244, "lng": 3.3792})


def estimate_congestion(time_str: Optional[str]) -> str:
    """
    Estimate congestion level from time of day.
    Peak hours → High, shoulders → Medium, off-peak → Low.
    """
    if not time_str:
        hour = int(time.strftime("%H"))
    else:
        try:
            hour = int(time_str.split(":")[0])
        except Exception:
            hour = 8

    if 7 <= hour <= 9 or 17 <= hour <= 19:
        return "High"
    elif 10 <= hour <= 16 or 20 <= hour <= 21:
        return "Medium"
    else:
        return "Low"


