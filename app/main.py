import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.models import PredictRequest, ReportRequest
from app.geocode import geocode_location
from app.routing import get_route
from app.congestion import estimate_commute
from app.safety import estimate_safety_score
from app.storage import save_report, list_reports

app = FastAPI(title="CommuteIQ API")

ALLOWED_ORIGINS = [
    "http://localhost:5173",
    os.getenv("FRONTEND_URL", "https://commuteiq.vercel.app"),
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/predict")
async def predict(req: PredictRequest):
    try:
        origin_coords = await geocode_location(req.origin, req.city)
        destination_coords = await geocode_location(req.destination, req.city)
        route = await get_route(origin_coords, destination_coords, req.mode)
        commute = estimate_commute(route["base_duration_minutes"], req.mode, req.time)
        safety = estimate_safety_score(req.city, req.mode)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception:
        raise HTTPException(status_code=502, detail="Upstream routing/geocoding service failed")

    quality = commute["quality"]
    explanation = (
        f"Heavy congestion expected on this route. Consider leaving earlier or trying an alternative mode."
        if quality == "poor"
        else f"Conditions look manageable. Safety score is {safety['safety_score']}/100 based on regional road-safety data."
    )
    departure_advice = "Wait 20 min, or use an alternative route" if quality == "poor" else "Leave now"

    return {
        "originCoords": origin_coords,
        "destinationCoords": destination_coords,
        "distanceKm": round(route["distance_km"], 1),
        "etaMinutes": commute["eta_minutes"],
        "quality": quality,
        "isEstimated": commute["is_estimated"],
        "safetyScore": safety["safety_score"],
        "safetyBasis": safety["safety_basis"],
        "explanation": explanation,
        "departureAdvice": departure_advice,
        "city": req.city,
        "mode": req.mode,
    }


@app.post("/reports")
async def create_report(req: ReportRequest):
    result = await save_report(req.model_dump())
    return result


@app.get("/reports")
async def get_reports(city: str | None = None):
    return await list_reports(city)
