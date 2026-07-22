"""Safety scoring, grounded in real published road-safety data rather than
an arbitrary guess. This is a country/mode-level baseline, not a per-route
measurement — a genuine per-corridor score would need a geocoded crash
dataset (Kenya has one; see NOTE below). Community reports submitted
through the app are the intended way to sharpen this over time toward
real per-route data.

Sources used:
- Kenya: ~28 road traffic fatalities per 100,000 people nationally
  (World Bank Smart and Safe Kenya Transport / WHO regional estimate).
  Boda-bodas are involved in a majority of Nairobi's reported crashes, and
  pedestrian/motorcyclist injuries rose over 250% from 2015-2020
  (NTSA data, reviewed in Tandfonline, 2020).
- Nigeria: FRSC/NBS reported 5,421 road deaths from 9,570 crashes
  nationally in 2024. The south-west zone (includes Lagos) recorded 661
  crashes and 316 deaths in Q2 2024 alone — a higher fatality-per-crash
  ratio than the national average, consistent with Lagos's dense,
  high-speed expressway traffic.

NOTE: The World Bank published a dataset of 30,000+ geocoded Nairobi
crashes (derived from crowdsourced @Ma3Route reports). Wiring that in
would let Kenya scores become genuinely per-corridor rather than a
country-level baseline — a good v2 improvement if there's time.
"""

# Baseline score out of 100 (higher = safer), reflecting relative national
# fatality-rate context. Not literally a percentage of anything — an
# ordinal baseline calibrated so the numbers feel meaningful relative to
# each other.
COUNTRY_BASELINE = {
    "nairobi": 68,
    "lagos": 58,
}

# Multiplicative adjustment per mode, reflecting relative risk within a
# country (e.g. boda-bodas/okadas carry disproportionate injury risk).
MODE_RISK_ADJUSTMENT = {
    "driving": 1.05,
    "walking": 0.95,
    "matatu": 1.0,
    "danfo": 1.0,
    "boda": 0.75,
}


def estimate_safety_score(city: str, mode: str) -> dict:
    baseline = COUNTRY_BASELINE.get(city, 60)
    adjustment = MODE_RISK_ADJUSTMENT.get(mode, 1.0)
    score = max(0, min(100, round(baseline * adjustment)))

    return {
        "safety_score": score,
        "safety_basis": "country_mode_baseline",  # flips to "community_data" once enough reports exist
    }
