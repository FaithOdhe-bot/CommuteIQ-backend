from pydantic import BaseModel
from typing import Optional


class PredictRequest(BaseModel):
    origin: str
    destination: str
    mode: str
    city: str
    time: Optional[str] = None


class ReportRequest(BaseModel):
    city: str
    type: str
    location: str
    lat: Optional[float] = None
    lng: Optional[float] = None
