"""
CommuteIQ — FastAPI Backend (v2)
main.py — Complete implementation with:
  - Mode-aware travel time prediction (Nigeria + Kenya transport modes)
  - Road quality integration
  - City validation
  - Alternative mode suggestions
  - Walking distance warnings
  - Full AI explanation engine
  - /recommend endpoint
  - Proper error handling

Endpoints:
  GET  /health    — health check + model status
  POST /predict   — full prediction with AI explanation
  POST /recommend — departure time recommendation
  POST /report    — submit community report
  GET  /reports   — list community reports
  GET  /modes     — list available modes per city
"""

import os
import time
import joblib
import httpx
from pathlib import Path
from typing import Optional, List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from models  import PredictRequest, ReportRequest
from routing import get_route
from storage import save_report, list_reports


# ── App ──────────────────────────────────────────────────────

app = FastAPI(
    title="CommuteIQ",
    description="Community-powered AI mobility assistant for African cities",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Model loading ─────────────────────────────────────────────

MODELS_DIR = Path(__file__).parent.parent / "models"

def load_models():
    try:
        travel_model      = joblib.load(MODELS_DIR / "travel_time_model.pkl")
        quality_model     = joblib.load(MODELS_DIR / "commute_quality_model.pkl")
        safety_scores     = joblib.load(MODELS_DIR / "safety_scores.pkl")
        encoders          = joblib.load(MODELS_DIR / "encoders.pkl")
        road_quality      = joblib.load(MODELS_DIR / "road_quality.pkl")
        transport_modes   = joblib.load(MODELS_DIR / "transport_modes.pkl")
        print("✅ All models loaded")
        return travel_model, quality_model, safety_scores, encoders, road_quality, transport_modes
    except FileNotFoundError as e:
        print(f"⚠️  Model not found: {e}. Run train_models.py first.")
        return None, None, None, None, None, None

(travel_model, quality_model,
 safety_scores, encoders,
 road_quality, transport_modes) = load_models()


# ── City helpers ──────────────────────────────────────────────

CITY_COORDS = {
    "lagos":        {"lat": 6.5244,  "lng": 3.3792},
    "abuja":        {"lat": 9.0765,  "lng": 7.3986},
    "kano":         {"lat": 12.0022, "lng": 8.5920},
    "ibadan":       {"lat": 7.3775,  "lng": 3.9470},
    "port harcourt":{"lat": 4.8156,  "lng": 7.0498},
    "enugu":        {"lat": 6.4584,  "lng": 7.5464},
    "nairobi":      {"lat": -1.2921, "lng": 36.8219},
    "mombasa":      {"lat": -4.0435, "lng": 39.6682},
    "kisumu":       {"lat": -0.0917, "lng": 34.7680},
    "nakuru":       {"lat": -0.3031, "lng": 36.0800},
    "eldoret":      {"lat": 0.5143,  "lng": 35.2698},
}

def get_country(city: str) -> str:
    if encoders:
        return encoders.get("city_to_country", {}).get(city.lower(), "nigeria")
    return "kenya" if city.lower() in ["nairobi","mombasa","kisumu","nakuru","eldoret"] else "nigeria"

def validate_mode_for_city(mode: str, city: str) -> tuple[bool, str]:
    """Check if mode is available in city. Returns (valid, suggestion)."""
    if not transport_modes:
        return True, ""
    country = get_country(city)
    country_modes = transport_modes.get(country, {})
    if mode.lower() in country_modes:
        return True, ""
    # Suggest correct alternatives
    available = list(country_modes.keys())
    return False, f"'{mode}' is not available in {city.title()}. Available: {', '.join(available)}"

def get_road_quality_score(city: str, road_name: Optional[str] = None) -> float:
    if not road_quality:
        return 50.0
    country = get_country(city)
    # Try named road first
    if road_name:
        road_lower = road_name.lower().strip()
        named = road_quality.get(country, {})
        if road_lower in named:
            return named[road_lower]
    # Fall back to city average
    return road_quality.get("city_avg", {}).get(city.lower(), 50.0)


# ── Weather ───────────────────────────────────────────────────

WEATHER_API = "https://api.open-meteo.com/v1/forecast"

async def get_weather(lat: float, lng: float) -> dict:
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(WEATHER_API, params={
                "latitude": lat, "longitude": lng,
                "current_weather": True,
                "hourly": "precipitation",
            })
            data = r.json()
            code = data.get("current_weather", {}).get("weathercode", 0)
            wind = data.get("current_weather", {}).get("windspeed", 0)
            if code in [51,53,55,61,63,65,80,81,82]: label = "Rainy"
            elif code in [45,48]:                     label = "Foggy"
            elif code in [1,2,3]:                     label = "Cloudy"
            else:                                     label = "Clear"
            return {"label": label, "code": code, "wind_kmh": wind}
    except Exception:
        return {"label": "Clear", "code": 0, "wind_kmh": 0}


# ── Congestion ────────────────────────────────────────────────

def estimate_congestion(time_str: Optional[str]) -> str:
    try:
        hour = int(time_str.split(":")[0]) if time_str else int(time.strftime("%H"))
    except Exception:
        hour = 8
    if 7 <= hour <= 9 or 17 <= hour <= 19:   return "High"
    elif 10 <= hour <= 16 or 20 <= hour <= 21: return "Medium"
    else:                                       return "Low"


# ── Geocoding ─────────────────────────────────────────────────

async def geocode_place(place: str, city: str) -> dict:
    try:
        async with httpx.AsyncClient(
            timeout=6, headers={"User-Agent": "SmartCommuteAI/2.0"}
        ) as client:
            r = await client.get(
                "https://nominatim.openstreetmap.org/search",
                params={"q": f"{place}, {city}", "format": "json", "limit": 1},
            )
            results = r.json()
            if results:
                return {"lat": float(results[0]["lat"]), "lng": float(results[0]["lon"])}
    except Exception:
        pass
    return CITY_COORDS.get(city.lower(), {"lat": 6.5244, "lng": 3.3792})


# ── ML prediction ─────────────────────────────────────────────

def predict_travel_time(
    distance_km: float, congestion: str, weather: str,
    alternatives: int, mode: str, city: str, rq_score: float
) -> float:
    """Predict travel time using ML model with mode + city + road quality."""
    cmap = encoders["congestion_map"] if encoders else {"Low":0,"Medium":1,"High":2}
    wmap = encoders["weather_map"]    if encoders else {"Clear":0,"Cloudy":1,"Foggy":2,"Rainy":3}
    mmap = encoders.get("mode_map",   {}) if encoders else {}
    cimap= encoders.get("city_map",   {}) if encoders else {}

    c_enc   = cmap.get(congestion, 1)
    w_enc   = wmap.get(weather, 0)
    m_enc   = mmap.get(mode.lower(), 0)
    ci_enc  = cimap.get(get_country(city), 0)
    is_peak = int(c_enc >= 1 and w_enc >= 1)

    features = [[distance_km, c_enc, w_enc, alternatives, is_peak, m_enc, ci_enc, rq_score]]

    if travel_model is None:
        # Fallback formula using transport_modes
        return _formula_travel_time(distance_km, congestion, weather, mode, city)

    try:
        return round(float(travel_model.predict(features)[0]), 1)
    except Exception:
        return _formula_travel_time(distance_km, congestion, weather, mode, city)


def _formula_travel_time(distance_km, congestion, weather, mode, city):
    """Formula fallback when model unavailable."""
    if not transport_modes:
        base_speed = 30.0
    else:
        country   = get_country(city)
        mode_data = transport_modes.get(country, {}).get(mode.lower(),
                    transport_modes.get(country, {}).get("driving", {}))
        speeds    = mode_data.get("avg_speed_kmh", {"urban": 30})
        base_speed = list(speeds.values())[min(2, len(speeds)-1)]

        peak_m = mode_data.get("peak_multiplier", 0.6)
        rain_m = mode_data.get("rain_multiplier", 0.8)

        if congestion == "High":   base_speed *= peak_m
        elif congestion == "Medium": base_speed *= (1 + peak_m) / 2
        if weather in ["Rainy","Foggy"]: base_speed *= rain_m

    t = (distance_km / max(base_speed, 1)) * 60
    wait = 0
    if transport_modes:
        country   = get_country(city)
        mode_data = transport_modes.get(country, {}).get(mode.lower(), {})
        wait      = mode_data.get("wait_time_min", 0)
    return round(t + wait, 1)


def get_commute_quality(
    congestion: str, weather: str, community_reports: int,
    safety_score: float, mode: str, city: str,
    distance_km: float, rq_score: float
) -> dict:
    """ML quality prediction with rule fallback."""
    if quality_model and encoders:
        try:
            cmap  = encoders["congestion_map"]
            wmap  = encoders["weather_map"]
            mmap  = encoders.get("mode_map", {})
            cimap = encoders.get("city_map", {})
            c_enc = cmap.get(congestion, 1)
            w_enc = wmap.get(weather, 0)
            m_enc = mmap.get(mode.lower(), 0)
            ci_enc= cimap.get(get_country(city), 0)
            is_pk = int(c_enc >= 1 and w_enc >= 1)
            feat  = [[distance_km, c_enc, w_enc, 2, is_pk, m_enc, ci_enc, rq_score]]
            pred  = int(quality_model.predict(feat)[0])
            label = encoders["quality_labels"][pred]
            emoji = encoders["quality_emoji"][pred]
            score = {2: 90, 1: 60, 0: 30}[pred]
            return {"label": label, "emoji": emoji, "score": score}
        except Exception:
            pass

    # Rule fallback
    bad_weather  = weather in ["Rainy","Foggy"]
    high_traffic = congestion == "High"
    low_safety   = safety_score < 50
    if high_traffic or (bad_weather and community_reports >= 1) or community_reports >= 3:
        return {"label":"Poor",     "emoji":"🔴","score":30}
    elif congestion=="Medium" or bad_weather or community_reports>=1 or low_safety:
        return {"label":"Moderate", "emoji":"🟡","score":60}
    else:
        return {"label":"Good",     "emoji":"🟢","score":90}


def get_safety_score(city: str, mode: str) -> float:
    if not safety_scores:
        return 65.0
    mult_map = transport_modes.get("safety_multipliers", {}) if transport_modes else {}
    base = safety_scores.get(city.lower(),
           safety_scores.get(get_country(city)[:3], 60.0))
    mult = mult_map.get(mode.lower(), 1.0)
    return round(min(100, max(0, base * mult)), 1)


# ── Alternative mode suggestion ───────────────────────────────

def suggest_alternative_mode(
    mode: str, city: str, congestion: str,
    weather: str, distance_km: float
) -> Optional[str]:
    """Suggest a better mode given current conditions."""
    if not transport_modes:
        return None
    country      = get_country(city)
    country_modes= transport_modes.get(country, {})
    current_mult = transport_modes.get("speed_multipliers", {}).get(mode.lower(), 1.0)
    rain         = weather in ["Rainy","Foggy"]
    high_traffic = congestion == "High"

    # Walking distance warning
    if mode.lower() == "walking":
        max_km = country_modes.get("walking", {}).get("max_recommended_km", 3.0)
        if distance_km > max_km:
            modes = [m for m in country_modes if m != "walking"]
            best  = min(modes, key=lambda m:
                transport_modes.get("speed_multipliers", {}).get(m, 0.5))
            info  = country_modes.get(best, {})
            return (f"⚠️ {distance_km:.1f}km is too far to walk safely. "
                    f"Consider {info.get('emoji','')} {info.get('label', best)} instead.")

    # Okada/boda in rain warning
    if mode.lower() in ["okada","boda_boda","boda"] and rain:
        safe_alt = "brt" if country == "nigeria" else "matatu"
        info = country_modes.get(safe_alt, {})
        return (f"⚠️ {country_modes[mode.lower()]['label']} in rain is dangerous. "
                f"Consider {info.get('emoji','')} {info.get('label', safe_alt)} for safety.")

    # BRT is faster than danfo in high traffic (Lagos)
    if mode.lower() == "danfo" and high_traffic and "brt" in country_modes:
        info = country_modes["brt"]
        return (f"💡 {info.get('emoji','')} {info.get('label','BRT')} has dedicated lanes — "
                f"likely faster than Danfo in current traffic.")

    return None


# ── Departure advice ──────────────────────────────────────────

def get_departure_advice(
    congestion: str, weather: str, travel_time: float, mode: str
) -> str:
    if congestion == "High" and weather in ["Rainy","Foggy"]:
        saved = round(travel_time * 0.30)
        return f"Wait 20 min — leaving later could save ~{saved} min on this route."
    elif congestion == "High":
        saved = round(travel_time * 0.20)
        return f"Wait 15 min — conditions may ease and save ~{saved} min."
    elif weather in ["Rainy","Foggy"]:
        return "Leave now but allow extra time — weather is reducing speeds."
    else:
        return "Leave now — conditions are good."


# ── AI Explanation ────────────────────────────────────────────

def generate_ai_explanation(
    origin: str, destination: str, travel_time: float,
    quality: dict, safety_score: float, weather: str,
    congestion: str, community_reports: int,
    departure_advice: str, mode: str, city: str,
    distance_km: float, rq_score: float,
    alt_suggestion: Optional[str]
) -> str:
    lines = []
    country      = get_country(city)
    mode_data    = (transport_modes or {}).get(country, {}).get(mode.lower(), {})
    mode_label   = mode_data.get("label", mode.title())
    mode_emoji   = mode_data.get("emoji", "")

    # Opening
    lines.append(
        f"Route {origin} → {destination}: {travel_time:.0f} min by "
        f"{mode_emoji} {mode_label} ({distance_km:.1f}km)."
    )

    # Weather
    if weather == "Rainy":
        lines.append("Rain is affecting road visibility and speeds.")
    elif weather == "Foggy":
        lines.append("Fog is reducing visibility on this route.")

    # Congestion
    if congestion == "High":
        lines.append("Heavy traffic on this corridor.")
    elif congestion == "Medium":
        lines.append("Moderate congestion detected.")

    # Community reports
    if community_reports > 0:
        lines.append(
            f"{community_reports} community report"
            f"{'s' if community_reports > 1 else ''} filed on this route in the last hour."
        )

    # Road quality context
    if rq_score < 30:
        lines.append(f"Road quality is poor on this route ({rq_score:.0f}/100) — expect rough conditions.")
    elif rq_score > 70:
        lines.append(f"Road quality is good ({rq_score:.0f}/100).")

    # Mode-specific warning
    if mode.lower() in ["okada","boda_boda","boda"] and weather in ["Rainy","Foggy"]:
        lines.append(f"⚠️ {mode_label} in wet conditions carries elevated crash risk.")
    elif mode.lower() == "walking" and distance_km > 3:
        lines.append(f"⚠️ {distance_km:.1f}km is a long walk — consider a faster mode.")

    # Safety
    if safety_score >= 75:
        lines.append(f"Safety score {safety_score:.0f}/100 — relatively safe corridor.")
    elif safety_score >= 50:
        lines.append(f"Safety score {safety_score:.0f}/100 — exercise normal caution.")
    else:
        lines.append(
            f"Safety score {safety_score:.0f}/100 — elevated risk. "
            f"Drive carefully and stay alert."
        )

    # Quality verdict
    lines.append(f"Commute quality: {quality['emoji']} {quality['label']}.")

    # Departure advice
    if "Wait" in departure_advice:
        lines.append(departure_advice)

    # Alternative suggestion
    if alt_suggestion:
        lines.append(alt_suggestion)

    return " ".join(lines)


# ── Response models ───────────────────────────────────────────

class PredictResponse(BaseModel):
    travel_time_min:    float
    commute_quality:    str
    quality_emoji:      str
    quality_score:      int
    safety_score:       float
    weather:            str
    congestion:         str
    departure_advice:   str
    ai_explanation:     str
    distance_km:        Optional[float] = None
    community_reports:  int = 0
    road_quality_score: Optional[float] = None
    mode_label:         Optional[str] = None
    mode_emoji:         Optional[str] = None
    alt_suggestion:     Optional[str] = None

class RecommendRequest(BaseModel):
    origin:      str
    destination: str
    mode:        str
    city:        str
    time:        Optional[str] = None

class RecommendResponse(BaseModel):
    recommended_departure: str
    windows: List[dict]
    best_window: dict

class ModesResponse(BaseModel):
    city:    str
    country: str
    modes:   List[dict]


# ── Endpoints ─────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "version": "2.0.0",
        "models": {
            "travel_time":       travel_model is not None,
            "commute_quality":   quality_model is not None,
            "safety_scores":     safety_scores is not None,
            "road_quality":      road_quality is not None,
            "transport_modes":   transport_modes is not None,
        },
        "supported_cities": list(CITY_COORDS.keys()),
    }


@app.get("/modes")
async def get_modes(city: str):
    """Return available transport modes for a city."""
    country      = get_country(city.lower())
    country_modes= (transport_modes or {}).get(country, {})
    modes_list   = [
        {
            "key":   key,
            "label": v.get("label", key),
            "emoji": v.get("emoji", ""),
            "description": v.get("description", ""),
        }
        for key, v in country_modes.items()
        if isinstance(v, dict)
    ]
    return ModesResponse(city=city, country=country, modes=modes_list)


@app.post("/predict", response_model=PredictResponse)
async def predict(req: PredictRequest):
    """Main prediction endpoint."""

    city    = req.city.lower().strip()
    mode    = req.mode.lower().strip()
    country = get_country(city)

    # Validate city
    if city not in CITY_COORDS:
        raise HTTPException(
            status_code=400,
            detail=f"City '{city}' not supported. Supported: {list(CITY_COORDS.keys())}"
        )

    # Validate mode for city
    mode_valid, mode_msg = validate_mode_for_city(mode, city)
    if not mode_valid:
        raise HTTPException(status_code=400, detail=mode_msg)

    # Mode metadata
    mode_data  = (transport_modes or {}).get(country, {}).get(mode, {})
    mode_label = mode_data.get("label", mode.title())
    mode_emoji = mode_data.get("emoji", "")

    # 1. Route
    try:
        origin_coords = await geocode_place(req.origin, city)
        dest_coords   = await geocode_place(req.destination, city)
        route         = await get_route(origin_coords, dest_coords, mode)
        distance_km   = route["distance_km"]
    except Exception:
        distance_km = 12.0   # reasonable urban fallback

    # 2. Weather
    coords      = CITY_COORDS.get(city, {"lat": 6.5244, "lng": 3.3792})
    weather_data= await get_weather(coords["lat"], coords["lng"])
    weather     = weather_data["label"]

    # 3. Congestion
    congestion = estimate_congestion(req.time)

    # 4. Community reports
    reports = await list_reports(city)
    cutoff  = time.time() - 3600
    community_count = len([
        r for r in reports
        if r.get("type") in ["accident","flood","road_closure","heavy_traffic"]
        and r.get("created_at", 0) > cutoff
    ])

    # 5. Road quality
    rq_score = get_road_quality_score(city)

    # 6. ML predictions
    travel_time  = predict_travel_time(
        distance_km, congestion, weather, 2, mode, city, rq_score
    )
    safety_score = get_safety_score(city, mode)
    quality      = get_commute_quality(
        congestion, weather, community_count,
        safety_score, mode, city, distance_km, rq_score
    )

    # 7. Departure advice
    departure_advice = get_departure_advice(congestion, weather, travel_time, mode)

    # 8. Alternative suggestion
    alt_suggestion = suggest_alternative_mode(mode, city, congestion, weather, distance_km)

    # 9. AI explanation
    ai_explanation = generate_ai_explanation(
        origin=req.origin, destination=req.destination,
        travel_time=travel_time, quality=quality,
        safety_score=safety_score, weather=weather,
        congestion=congestion, community_reports=community_count,
        departure_advice=departure_advice, mode=mode,
        city=city, distance_km=distance_km,
        rq_score=rq_score, alt_suggestion=alt_suggestion,
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
        road_quality_score=round(rq_score, 1),
        mode_label=mode_label,
        mode_emoji=mode_emoji,
        alt_suggestion=alt_suggestion,
    )


@app.post("/recommend", response_model=RecommendResponse)
async def recommend(req: RecommendRequest):
    """Departure time recommendation across 4 time windows."""

    city    = req.city.lower().strip()
    mode    = req.mode.lower().strip()
    coords  = CITY_COORDS.get(city, {"lat": 6.5244, "lng": 3.3792})
    rq_score= get_road_quality_score(city)

    try:
        o_coords = await geocode_place(req.origin, city)
        d_coords = await geocode_place(req.destination, city)
        route    = await get_route(o_coords, d_coords, mode)
        distance = route["distance_km"]
    except Exception:
        distance = 12.0

    weather_data = await get_weather(coords["lat"], coords["lng"])
    weather      = weather_data["label"]

    # Evaluate 4 departure windows
    current_hour = int(time.strftime("%H"))
    windows = []
    for offset in [0, 15, 30, 60]:
        hour      = (current_hour + offset // 60) % 24
        cong      = estimate_congestion(f"{hour}:00")
        t         = predict_travel_time(distance, cong, weather, 2, mode, city, rq_score)
        safety    = get_safety_score(city, mode)
        quality   = get_commute_quality(cong, weather, 0, safety, mode, city, distance, rq_score)
        windows.append({
            "label":        f"{'Now' if offset==0 else f'+{offset} min'}",
            "offset_min":   offset,
            "congestion":   cong,
            "travel_time":  t,
            "quality":      quality["label"],
            "emoji":        quality["emoji"],
            "score":        quality["score"],
        })

    best   = min(windows, key=lambda w: w["travel_time"])
    advice = (
        f"Leave now" if best["offset_min"] == 0
        else f"Wait {best['offset_min']} min — saves ~{windows[0]['travel_time'] - best['travel_time']:.0f} min"
    )

    return RecommendResponse(
        recommended_departure=advice,
        windows=windows,
        best_window=best,
    )


@app.post("/report")
async def submit_report(req: ReportRequest):
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
    reports = await list_reports(city)
    cutoff  = time.time() - (6 * 3600)
    recent  = [r for r in reports if r.get("created_at", 0) > cutoff]
    return {"reports": recent, "count": len(recent)}


