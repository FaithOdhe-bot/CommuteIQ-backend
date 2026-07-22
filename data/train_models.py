"""
SmartCommute AI — Flexible Multi-Dataset Model Training Script
==============================================================

Supports any combination of these dataset types:
  1. Nigeria Traffic CSV  — structured with Congestion, Weather, Travel Time columns
  2. Nairobi Driving OD  — folder of time-series origin-destination matrices (driving)
  3. Nairobi Matatu OD   — folder of origin-destination matrices (matatu + walk)
  4. Crash CSV           — state-level crash data for safety scoring
  5. Generic CSV         — any CSV you map via --schema flag

Usage examples:
  # Train on Nigeria data only (default)
  python train_models.py

  # Add Nairobi driving OD folder
  python train_models.py --nairobi-driving data/nairobi-driving/

  # Add matatu folder
  python train_models.py --nairobi-matatu data/nairobi-matatus-extended/

  # All sources together
  python train_models.py \\
    --nigeria  data/nigeria_traffic_data.csv \\
    --crashes  data/Nigerian_Road_Traffic_Crashes_2020_2024.csv \\
    --nairobi-driving data/nairobi-driving/ \\
    --nairobi-matatu  data/nairobi-matatus-extended/ \\
    --generic  data/my_extra_data.csv --schema generic_schema.json

  # Multiple generic CSVs
  python train_models.py --generic data/file1.csv data/file2.csv

Output:
  models/travel_time_model.pkl
  models/safety_scores.pkl
  models/encoders.pkl
"""

import os
import sys
import json
import glob
import argparse
import warnings
import zipfile
import io

import pandas as pd
import numpy as np
import joblib

from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, classification_report
from xgboost import XGBRegressor

warnings.filterwarnings("ignore")
os.makedirs("models", exist_ok=True)


# ─── UNIFIED SCHEMA ──────────────────────────────────────────────────────────
# Every dataset is normalized to these columns before training.
# distance_km | congestion_enc | weather_enc | alternatives | is_peak | travel_time_min | mode | city

CONGESTION_MAP = {"Low": 0, "Medium": 1, "High": 2}
WEATHER_MAP    = {"Clear": 0, "Cloudy": 1, "Foggy": 2, "Rainy": 3}
FEATURES       = ["distance_km", "congestion_enc", "weather_enc", "alternatives", "is_peak"]


# ─── DATASET LOADERS ─────────────────────────────────────────────────────────

def load_nigeria_traffic(path: str) -> pd.DataFrame:
    """
    Load Nigeria traffic CSV.
    Expected columns: Road Length (km), Congestion Level, Weather,
                      Travel Time (min), Alternative Routes
    """
    print(f"  Loading Nigeria traffic: {path}")
    df = pd.read_csv(path)

    required = {"Road Length (km)", "Congestion Level", "Weather", "Travel Time (min)"}
    missing  = required - set(df.columns)
    if missing:
        raise ValueError(f"Nigeria CSV missing columns: {missing}")

    out = pd.DataFrame()
    out["distance_km"]     = df["Road Length (km)"]
    out["congestion_enc"]  = df["Congestion Level"].map(CONGESTION_MAP).fillna(1)
    out["weather_enc"]     = df["Weather"].map(WEATHER_MAP).fillna(0)
    out["alternatives"]    = df.get("Alternative Routes", pd.Series([2]*len(df)))
    out["travel_time_min"] = df["Travel Time (min)"]
    out["is_peak"]         = ((out["congestion_enc"] >= 1) & (out["weather_enc"] >= 1)).astype(int)
    out["mode"]            = "driving"
    out["city"]            = "nigeria"
    out = out.dropna(subset=["distance_km", "travel_time_min"])
    print(f"    ✅ {len(out)} rows loaded")
    return out


def load_nairobi_od_folder(folder_path: str, mode: str = "driving") -> pd.DataFrame:
    """
    Load Nairobi OD matrix folder.
    Each CSV is a time-series matrix: rows=time slots, cols=destination IDs.
    Values are travel times in SECONDS. We extract them as individual trip records
    and synthesize congestion/weather based on time slot index.

    Time slot mapping (based on Rising & Campbell 2017 methodology):
      Slots 0-1  → 06:00-08:00 → peak morning  → High congestion
      Slots 2-3  → 09:00-11:00 → shoulder      → Medium
      Slots 4-5  → 12:00-14:00 → midday        → Low
      Slots 6-7  → 16:00-18:00 → peak evening  → High
      Slot  8    → 19:00+      → off-peak       → Low
    """
    print(f"  Loading Nairobi OD matrices ({mode}): {folder_path}")

    congestion_by_slot = {0: 2, 1: 2, 2: 1, 3: 1, 4: 0, 5: 0, 6: 2, 7: 2, 8: 0}

    csv_files = sorted(glob.glob(os.path.join(folder_path, "*.csv")))
    # Skip the master matrix file (no numeric filename suffix like driving.csv)
    csv_files = [f for f in csv_files if os.path.basename(f).replace(".csv","").replace("driving-","").replace("matonwalk-","").isdigit()]

    if not csv_files:
        print(f"    ⚠️  No individual OD files found in {folder_path}")
        return pd.DataFrame()

    # Sample up to 200 files to keep training fast
    if len(csv_files) > 200:
        import random
        random.seed(42)
        csv_files = random.sample(csv_files, 200)

    records = []
    for fpath in csv_files:
        try:
            df = pd.read_csv(fpath, header=0)
            values = df.values.astype(float)
            n_slots = min(values.shape[0], 9)

            for slot_idx in range(n_slots):
                row_vals = values[slot_idx]
                row_vals = row_vals[~np.isnan(row_vals)]
                congestion_enc = congestion_by_slot.get(slot_idx, 1)
                # Synthesize approximate distance from travel time
                # Nairobi avg speed ~30 km/h driving, ~10 km/h matatu+walk
                avg_speed_kmh = 30.0 if mode == "driving" else 12.0

                for travel_sec in row_vals:
                    travel_min = travel_sec / 60.0
                    if travel_min < 2 or travel_min > 180:
                        continue  # skip outliers
                    distance_km = (travel_min / 60.0) * avg_speed_kmh

                    records.append({
                        "distance_km":     round(distance_km, 2),
                        "congestion_enc":  congestion_enc,
                        "weather_enc":     0,   # no weather in this dataset, default Clear
                        "alternatives":    1,
                        "travel_time_min": round(travel_min, 1),
                        "is_peak":         int(congestion_enc == 2),
                        "mode":            mode,
                        "city":            "nairobi",
                    })
        except Exception:
            continue

    out = pd.DataFrame(records)
    print(f"    ✅ {len(out)} trip records extracted from {len(csv_files)} files")
    return out


def load_nairobi_od_zip(zip_path: str) -> pd.DataFrame:
    """
    Load Nairobi OD data directly from a zip file.
    Auto-detects driving and matatu folders inside the zip.
    """
    print(f"  Loading Nairobi OD data from zip: {zip_path}")
    all_records = []

    with zipfile.ZipFile(zip_path, "r") as z:
        all_names = z.namelist()

        # driving files
        driving_files = [n for n in all_names
                         if "nairobi-driving/" in n
                         and n.endswith(".csv")
                         and os.path.basename(n).replace("driving-","").replace(".csv","").isdigit()]

        # matatu files
        matatu_files = [n for n in all_names
                        if "nairobi-matatus-extended/" in n
                        and n.endswith(".csv")
                        and os.path.basename(n).replace("matonwalk-","").replace(".csv","").isdigit()]

        congestion_by_slot = {0: 2, 1: 2, 2: 1, 3: 1, 4: 0, 5: 0, 6: 2, 7: 2, 8: 0}

        def extract_records(file_list, mode, avg_speed_kmh, sample_size=150):
            import random
            random.seed(42)
            if len(file_list) > sample_size:
                file_list = random.sample(file_list, sample_size)
            records = []
            for fname in file_list:
                try:
                    with z.open(fname) as f:
                        df = pd.read_csv(f, header=0)
                    values = df.values.astype(float)
                    n_slots = min(values.shape[0], 9)
                    for slot_idx in range(n_slots):
                        row_vals = values[slot_idx]
                        row_vals = row_vals[~np.isnan(row_vals)]
                        congestion_enc = congestion_by_slot.get(slot_idx, 1)
                        for travel_sec in row_vals:
                            travel_min = travel_sec / 60.0
                            if travel_min < 2 or travel_min > 180:
                                continue
                            distance_km = (travel_min / 60.0) * avg_speed_kmh
                            records.append({
                                "distance_km":     round(distance_km, 2),
                                "congestion_enc":  congestion_enc,
                                "weather_enc":     0,
                                "alternatives":    1,
                                "travel_time_min": round(travel_min, 1),
                                "is_peak":         int(congestion_enc == 2),
                                "mode":            mode,
                                "city":            "nairobi",
                            })
                except Exception:
                    continue
            return records

        if driving_files:
            recs = extract_records(driving_files, "driving", avg_speed_kmh=30.0)
            print(f"    ✅ {len(recs)} driving records from {min(len(driving_files),150)} files")
            all_records.extend(recs)

        if matatu_files:
            recs = extract_records(matatu_files, "matatu", avg_speed_kmh=12.0)
            print(f"    ✅ {len(recs)} matatu records from {min(len(matatu_files),150)} files")
            all_records.extend(recs)

    return pd.DataFrame(all_records)


def load_generic_csv(path: str, schema: dict = None) -> pd.DataFrame:
    """
    Load any CSV and map its columns to the unified schema.
    schema is a dict mapping unified column names to actual column names, e.g.:
    {
      "distance_km":     "distance",
      "travel_time_min": "duration_min",
      "congestion_enc":  "traffic_level",   ← optional, synthesized if missing
      "weather_enc":     "weather_code"      ← optional, synthesized if missing
    }
    If no schema is given, the script tries to auto-detect columns.
    """
    print(f"  Loading generic CSV: {path}")
    df = pd.read_csv(path)
    print(f"    Columns found: {df.columns.tolist()}")

    out = pd.DataFrame()

    if schema:
        # Map columns using provided schema
        col_map = schema.get("columns", {})
        out["distance_km"]     = df[col_map.get("distance_km", "distance_km")]
        out["travel_time_min"] = df[col_map.get("travel_time_min", "travel_time_min")]

        # Optional columns with sensible defaults
        if col_map.get("congestion_enc") and col_map["congestion_enc"] in df:
            raw = df[col_map["congestion_enc"]]
            if raw.dtype == object:
                out["congestion_enc"] = raw.map(CONGESTION_MAP).fillna(1)
            else:
                out["congestion_enc"] = raw.fillna(1)
        else:
            out["congestion_enc"] = 1  # default Medium

        if col_map.get("weather_enc") and col_map["weather_enc"] in df:
            raw = df[col_map["weather_enc"]]
            if raw.dtype == object:
                out["weather_enc"] = raw.map(WEATHER_MAP).fillna(0)
            else:
                out["weather_enc"] = raw.fillna(0)
        else:
            out["weather_enc"] = 0  # default Clear

        out["alternatives"] = df.get(col_map.get("alternatives", "__missing__"), pd.Series([2]*len(df)))

    else:
        # Auto-detect common column name patterns
        col_lower = {c.lower().replace(" ","_"): c for c in df.columns}

        dist_col  = next((col_lower[k] for k in col_lower if "distance" in k or "length" in k or "km" in k), None)
        time_col  = next((col_lower[k] for k in col_lower if "travel_time" in k or "duration" in k or "time_min" in k), None)
        cong_col  = next((col_lower[k] for k in col_lower if "congestion" in k or "traffic" in k), None)
        wthr_col  = next((col_lower[k] for k in col_lower if "weather" in k or "rain" in k), None)
        alt_col   = next((col_lower[k] for k in col_lower if "alternative" in k), None)

        if not dist_col or not time_col:
            raise ValueError(
                f"Cannot auto-detect required columns in {path}.\n"
                f"Please provide a schema JSON with --schema. Available columns: {df.columns.tolist()}"
            )

        out["distance_km"]     = df[dist_col]
        out["travel_time_min"] = df[time_col]
        out["congestion_enc"]  = df[cong_col].map(CONGESTION_MAP).fillna(1) if cong_col else 1
        out["weather_enc"]     = df[wthr_col].map(WEATHER_MAP).fillna(0)   if wthr_col else 0
        out["alternatives"]    = df[alt_col].fillna(2) if alt_col else 2

    out["is_peak"] = ((out["congestion_enc"] >= 1) & (out["weather_enc"] >= 1)).astype(int)
    out["mode"]    = schema.get("mode", "driving") if schema else "driving"
    out["city"]    = schema.get("city", "unknown") if schema else "unknown"
    out = out.dropna(subset=["distance_km", "travel_time_min"])
    print(f"    ✅ {len(out)} rows loaded")
    return out


def load_crash_data(path: str) -> dict:
    """Build safety scores from crash CSV."""
    print(f"  Loading crash data: {path}")
    df = pd.read_csv(path)

    state_stats = df.groupby("State").agg(
        total_crashes=("Total_Crashes", "sum"),
        total_injured=("Num_Injured",   "sum"),
        total_killed =("Num_Killed",    "sum"),
    ).reset_index()

    state_stats["risk_index"] = (
        state_stats["total_crashes"] * 1.0 +
        state_stats["total_injured"] * 1.0 +
        state_stats["total_killed"]  * 3.0
    )
    min_r = state_stats["risk_index"].min()
    max_r = state_stats["risk_index"].max()
    state_stats["safety_score"] = (
        100 - ((state_stats["risk_index"] - min_r) / (max_r - min_r) * 100)
    ).round(1)

    scores = dict(zip(state_stats["State"].str.lower(), state_stats["safety_score"]))
    scores["default"] = 60.0
    scores["nairobi"] = 68.0
    scores["lagos"]   = scores.get("lagos", 70.0)
    print(f"    ✅ {len(state_stats)} states scored")
    return scores


# ─── TRAINING ────────────────────────────────────────────────────────────────

def train_and_save(combined: pd.DataFrame, safety_scores: dict, encoders: dict):
    """Train both models on the combined dataset and save all pkl files."""

    print(f"\n── Dataset summary ──────────────────────────────────")
    print(f"  Total rows : {len(combined)}")
    print(f"  Cities     : {combined['city'].value_counts().to_dict()}")
    print(f"  Modes      : {combined['mode'].value_counts().to_dict()}")
    print(f"  Travel time: {combined['travel_time_min'].min():.0f} – {combined['travel_time_min'].max():.0f} min")
    print()

    X = combined[FEATURES]
    y_time = combined["travel_time_min"]

    X_tr, X_te, yt_tr, yt_te = train_test_split(X, y_time, test_size=0.2, random_state=42)

    # ── Model 1: Travel Time ────────────────────────────────────────────────
    print("── Training Model 1: Travel Time Prediction (XGBoost) ──")
    travel_model = XGBRegressor(
        n_estimators=300,
        max_depth=6,
        learning_rate=0.08,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        verbosity=0,
    )
    travel_model.fit(X_tr, yt_tr)
    mae = mean_absolute_error(yt_te, travel_model.predict(X_te))
    print(f"  MAE: {mae:.2f} minutes")
    joblib.dump(travel_model, "models/travel_time_model.pkl")
    print("  Saved → models/travel_time_model.pkl")

    # ── Safety Scores ───────────────────────────────────────────────────────
    joblib.dump(safety_scores, "models/safety_scores.pkl")
    print("\n  Saved → models/safety_scores.pkl")

    # ── Encoders & Metadata ─────────────────────────────────────────────────
    encoders.update({
        "congestion_map":  CONGESTION_MAP,
        "weather_map":     WEATHER_MAP,
        "features":        FEATURES,
        "quality_labels":  {0: "Poor", 1: "Moderate", 2: "Good"},
        "quality_emoji":   {0: "🔴",   1: "🟡",       2: "🟢"},
        "dataset_sources": combined["city"].unique().tolist(),
    })
    joblib.dump(encoders, "models/encoders.pkl")
    print("  Saved → models/encoders.pkl")

    print("\n✅ Training complete. All models saved to /models")


# ─── CLI ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="SmartCommute AI — flexible multi-dataset model trainer"
    )
    parser.add_argument("--nigeria",         type=str, default="data/nigeria_traffic_data.csv",
                        help="Path to Nigeria traffic CSV")
    parser.add_argument("--crashes",         type=str, default="data/Nigerian_Road_Traffic_Crashes_2020_2024.csv",
                        help="Path to crash CSV for safety scores")
    parser.add_argument("--nairobi-driving", type=str, default=None,
                        help="Path to folder of Nairobi driving OD CSVs")
    parser.add_argument("--nairobi-matatu",  type=str, default=None,
                        help="Path to folder of Nairobi matatu OD CSVs")
    parser.add_argument("--nairobi-zip",     type=str, default=None,
                        help="Path to TransportData.zip (auto-extracts both driving and matatu)")
    parser.add_argument("--generic",         type=str, nargs="+", default=[],
                        help="One or more generic CSV paths to include")
    parser.add_argument("--schema",          type=str, default=None,
                        help="Path to JSON schema file for generic CSVs")
    parser.add_argument("--skip-nigeria",    action="store_true",
                        help="Skip the default Nigeria CSV")

    args = parser.parse_args()

    frames = []
    safety_scores = {"default": 60.0, "nairobi": 68.0}
    encoders = {}

    # ── Load Nigeria traffic ────────────────────────────────────────────────
    if not args.skip_nigeria and os.path.exists(args.nigeria):
        frames.append(load_nigeria_traffic(args.nigeria))
    elif not args.skip_nigeria:
        print(f"  ⚠️  Nigeria CSV not found at {args.nigeria} — skipping")

    # ── Load crash data ─────────────────────────────────────────────────────
    if os.path.exists(args.crashes):
        safety_scores = load_crash_data(args.crashes)
    else:
        print(f"  ⚠️  Crash CSV not found at {args.crashes} — using defaults")

    # ── Load Nairobi zip (most convenient) ─────────────────────────────────
    if args.nairobi_zip and os.path.exists(args.nairobi_zip):
        frames.append(load_nairobi_od_zip(args.nairobi_zip))

    # ── Load Nairobi driving folder ─────────────────────────────────────────
    if args.nairobi_driving and os.path.exists(args.nairobi_driving):
        frames.append(load_nairobi_od_folder(args.nairobi_driving, mode="driving"))

    # ── Load Nairobi matatu folder ──────────────────────────────────────────
    if args.nairobi_matatu and os.path.exists(args.nairobi_matatu):
        frames.append(load_nairobi_od_folder(args.nairobi_matatu, mode="matatu"))

    # ── Load generic CSVs ───────────────────────────────────────────────────
    schema = None
    if args.schema and os.path.exists(args.schema):
        with open(args.schema) as f:
            schema = json.load(f)

    for gpath in args.generic:
        if os.path.exists(gpath):
            frames.append(load_generic_csv(gpath, schema=schema))
        else:
            print(f"  ⚠️  Generic CSV not found: {gpath}")

    # ── Combine ─────────────────────────────────────────────────────────────
    if not frames:
        print("❌ No datasets loaded. Check your file paths.")
        sys.exit(1)

    combined = pd.concat(frames, ignore_index=True)
    combined = combined.dropna(subset=FEATURES + ["travel_time_min"])

    # ── Train ────────────────────────────────────────────────────────────────
    train_and_save(combined, safety_scores, encoders)


if __name__ == "__main__":
    main()
