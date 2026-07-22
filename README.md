# 🚗 CommuteIQ — Backend

> **Community-powered AI mobility assistant for African cities.**  
> Built for the Girls in STEM Hackathon.

CommuteIQ combines ML travel time prediction, real African crash data safety scoring, live weather, and community-powered road reports to generate **personalized, AI-explained commute decisions** — built specifically for Lagos and Nairobi commuters.

---

## 🗂️ Project Structure

```
smartcommute-backend/
├── app/
│   ├── __init__.py
│   ├── main.py                   # FastAPI app — all endpoints
│   ├── models.py                 # Pydantic request/response schemas
│   ├── routing.py                # Real route distances via OSRM
│   ├── safety.py                 # Safety score baseline logic
│   ├── storage.py                # Supabase + in-memory community reports
│   ├── congestion.py             # Time-of-day congestion estimation
│   └── geocode.py                # Nominatim place → coordinates
│
├── models/                       # ⚠️ Gitignored — generate locally
│   ├── travel_time_model.pkl     # XGBoost travel time regressor
│   ├── commute_quality_model.pkl # Random Forest quality classifier
│   ├── safety_scores.pkl         # Safety scores by Nigerian state
│   └── encoders.pkl              # Feature encoders & metadata
│
├── data/                         # ⚠️ Gitignored — add your CSVs here
│   ├── nigeria_traffic_data.csv
│   ├── Nigerian_Road_Traffic_Crashes_2020_2024.csv
│   └── TransportData.zip         # Nairobi OD matrices (optional)
│
├── train_models.py               # Flexible multi-dataset model trainer
├── requirements.txt
├── .env.example
├── .gitignore
├── supabase_schema.sql
└── README.md
```

---

## ⚡ Quick Start

### 1. Clone the repo
```bash
git clone https://github.com/FaithOdhe-bot/CommuteIQ-backend.git
cd CommuteIQ-backend
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Add your data files
```
data/
├── nigeria_traffic_data.csv
├── Nigerian_Road_Traffic_Crashes_2020_2024.csv
└── TransportData.zip              # optional — Nairobi data
```

### 4. Train the ML models
```bash
# Nigeria data only (fastest)
python train_models.py

# Nigeria + Nairobi (recommended — larger dataset)
python train_models.py --nairobi-zip data/TransportData.zip
```
This generates the `/models/*.pkl` files the backend needs.

### 5. Set up environment variables
```bash
cp .env.example .env
# Then fill in your Supabase URL and KEY in .env
```

### 6. Start the server
```bash
uvicorn app.main:app --reload --port 8000
```

### 7. Test it's working
Open [http://localhost:8000/docs](http://localhost:8000/docs) — you should see the Swagger UI with all endpoints.

---

## 🤖 Training Options

`train_models.py` supports multiple dataset types. Use whichever you have:

| Command | Trains On |
|---|---|
| `python train_models.py` | Nigeria traffic only (default) |
| `python train_models.py --nairobi-zip data/TransportData.zip` | Nigeria + Nairobi driving + matatu |
| `python train_models.py --nairobi-driving data/nairobi-driving/` | Nigeria + Nairobi driving folder |
| `python train_models.py --nairobi-matatu data/nairobi-matatus-extended/` | Nigeria + Nairobi matatu folder |
| `python train_models.py --generic data/ghana.csv` | Nigeria + any extra CSV |
| `python train_models.py --generic data/accra.csv --schema schema.json` | Nigeria + CSV with custom columns |
| `python train_models.py --skip-nigeria --generic data/my_data.csv` | Train on your own data only |

### Adding a new dataset with different column names

Create a schema JSON file:
```json
{
  "mode": "driving",
  "city": "accra",
  "columns": {
    "distance_km":     "Road Length (km)",
    "travel_time_min": "Travel Time (min)",
    "congestion_enc":  "Congestion Level",
    "weather_enc":     "Weather",
    "alternatives":    "Alternative Routes"
  }
}
```
Then pass it: `python train_models.py --generic data/accra.csv --schema schema.json`

---

## 🔌 API Reference

### `GET /health`
Check if the backend is running and models are loaded.

**Response:**
```json
{
  "status": "ok",
  "models_loaded": true,
  "safety_scores_loaded": true
}
```

---

### `POST /predict`
Main prediction endpoint. Returns travel time, safety score, commute quality, and an AI-generated plain-language explanation.

**Request body:**
```json
{
  "origin":      "Victoria Island",
  "destination": "Ikeja",
  "mode":        "danfo",
  "city":        "lagos",
  "time":        "07:30"
}
```

**Supported modes:** `driving`, `danfo`, `matatu`, `boda`, `walking`, `rideshare`

**Supported cities:** `lagos`, `nairobi`, `abuja`, `kano`

**Response:**
```json
{
  "travel_time_min":   42,
  "commute_quality":   "Moderate",
  "quality_emoji":     "🟡",
  "quality_score":     60,
  "safety_score":      70.7,
  "weather":           "Rainy",
  "congestion":        "High",
  "departure_advice":  "Wait 15 min — conditions may ease and save ~8 min.",
  "ai_explanation":    "Route Victoria Island → Ikeja estimated at 42 min. Rain is currently affecting road visibility. Heavy traffic on this corridor. Safety score 70/100 — exercise normal caution. Overall commute quality: 🟡 Moderate.",
  "distance_km":       12.4,
  "community_reports": 2
}
```

---

### `POST /report`
Submit a community road report.

**Request body:**
```json
{
  "city":     "lagos",
  "type":     "flood",
  "location": "Lekki-Epe Expressway",
  "lat":      6.4698,
  "lng":      3.5852
}
```

**Report types:** `accident`, `flood`, `road_closure`, `heavy_traffic`, `construction`, `breakdown`

**Response:**
```json
{
  "ok": true,
  "message": "Report submitted. Thank you!",
  "storage": "supabase"
}
```

---

### `GET /reports?city=lagos`
Get recent community reports (last 6 hours), optionally filtered by city.

**Response:**
```json
{
  "reports": [
    {
      "city": "lagos",
      "type": "flood",
      "location": "Lekki-Epe Expressway",
      "lat": 6.4698,
      "lng": 3.5852,
      "created_at": 1721678400.0
    }
  ],
  "count": 1
}
```

---

## 🔐 Environment Variables

Copy `.env.example` to `.env` and fill in your values:

| Variable | Where to Get It | Required |
|---|---|---|
| `SUPABASE_URL` | Supabase dashboard → Project Settings → API → Project URL | Yes |
| `SUPABASE_KEY` | Supabase dashboard → Project Settings → API → anon/public key | Yes |

> **Without Supabase keys**, the app still works — community reports fall back to in-memory storage and reset on each server restart. You can set up Supabase anytime before Day 5.

---

## 🗄️ Database Setup (Supabase)

Run this SQL in your Supabase SQL editor to create the reports table:

```sql
create table reports (
  id         bigint generated always as identity primary key,
  city       text not null,
  type       text not null,
  location   text not null,
  lat        double precision,
  lng        double precision,
  timestamp  double precision,
  created_at double precision default extract(epoch from now())
);
```

---

## 🚀 Deployment

### Backend → Render (free tier)
1. Push your code to GitHub
2. Go to [render.com](https://render.com) → New Web Service → Connect your repo
3. Set build command: `pip install -r requirements.txt`
4. Set start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
5. Add environment variables: `SUPABASE_URL` and `SUPABASE_KEY`
6. Use Render Shell to run `python train_models.py` (since PKL files are gitignored)

### Frontend → Vercel (free tier)
1. Push frontend code to GitHub
2. Go to [vercel.com](https://vercel.com) → New Project → Import repo
3. Add environment variable: `VITE_API_URL` = your Render backend URL
4. Deploy — every push to `main` redeploys automatically

---

## 📊 Data Sources

| Dataset | Purpose | Source |
|---|---|---|
| Nigerian States Travel Data | Travel time ML training | Provided dataset |
| Nigerian Traffic Crashes 2020–2024 | Safety scoring | FRSC/NBS via Kaggle |
| Nairobi Driving OD Matrices | Nairobi travel time training | Rising & Campbell, 2017 (Zenodo) |
| Nairobi Matatu OD Matrices | Matatu travel time training | Rising & Campbell, 2017 (Zenodo) |
| OpenStreetMap / OSRM | Real road routing & distances | project-osrm.org (free) |
| Open-Meteo | Live weather | api.open-meteo.com (free, no key) |
| OpenStreetMap Nominatim | Place name geocoding | nominatim.openstreetmap.org (free) |

---

## 🏗️ ML Models

| Model | Type | Algorithm | Purpose |
|---|---|---|---|
| Travel Time Prediction | Regression | XGBoost | Predict journey time in minutes given distance, congestion, weather |
| Safety Scoring | Rule-based formula | Weighted crash index | Score each city/state 0–100 based on 4 years of crash records |
| Commute Quality | Rule-based logic | Congestion + weather + reports | Classify commute as 🟢 Good / 🟡 Moderate / 🔴 Poor |

> **Why rule-based for quality?** The Suitability Score in the Nigeria dataset does not vary meaningfully with congestion or weather, making ML unreliable for this label. Rule-based classification is more honest, explainable to judges, and performs better in practice.

---

## 👥 Team

| Member | Role | Responsibilities |
|---|---|---|
| AI Lead | Data & ML | Data cleaning, feature engineering, ML models, recommendation engine, AI explanations, Devpost write-up |
| Full-Stack Dev | Backend & Frontend | FastAPI backend, React frontend, database setup, API integrations, map rendering |

---

## 📝 License
Data sources are used under their respective open licenses (ODbL for OSM, MIT/CC for research datasets).
