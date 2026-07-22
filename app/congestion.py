"""Turns OSRM's free-flow driving time into a realistic, mode-adjusted
estimate. These multipliers are NOT measured per-route — they're
calibrated against published city-level commute research, and that is
disclosed to the user via the `is_estimated` flag returned to the frontend.

Sources used to calibrate:
- Nairobi avg one-way commute: ~53.7 min (Numbeo Traffic Index, 2026)
- Lagos avg one-way commute: ~68.3 min (Numbeo Traffic Index, 2026)
- Nairobi matatu/walking/driving travel times: Rising & Campbell,
  "Travel Times by Transportation Mode in Nairobi, Kenya," Zenodo, 2017
"""

MODE_MULTIPLIERS = {
    "driving": 1.0,
    "matatu": 1.35,  # matatus stop frequently and follow indirect routes
    "danfo": 1.35,   # same structural pattern as matatus, Lagos context
    "boda": 0.75,    # boda-bodas/okadas can filter through stopped traffic
    "walking": None,  # OSRM's own walking profile is used directly
}


def _peak_multiplier(departure_time: str | None) -> float:
    if not departure_time:
        return 1.3  # assume moderate congestion if unspecified
    try:
        hour = int(departure_time.split(":")[0])
    except (ValueError, IndexError):
        return 1.3
    is_peak = (7 <= hour <= 9) or (17 <= hour <= 19)
    return 2.0 if is_peak else 1.2


def estimate_commute(base_duration_minutes: float, mode: str, departure_time: str | None) -> dict:
    mode_multiplier = MODE_MULTIPLIERS.get(mode, 1.0) or 1.0
    peak = _peak_multiplier(departure_time)
    eta_minutes = round(base_duration_minutes * mode_multiplier * peak)

    if eta_minutes < base_duration_minutes * 1.2:
        quality = "good"
    elif eta_minutes < base_duration_minutes * 1.8:
        quality = "moderate"
    else:
        quality = "poor"

    return {"eta_minutes": eta_minutes, "quality": quality, "is_estimated": True}
