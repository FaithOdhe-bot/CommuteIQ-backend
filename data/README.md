# CommuteIQ — Backend

FastAPI backend providing real predictions: live geocoding (Nominatim),
real road routing (OSRM), a congestion model calibrated to published
Kenya/Nigeria commute research, and a country/mode safety baseline
grounded in real road-safety statistics (see app/safety.py for sources).

## Local setup
```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```
Visit http://localhost:8000/docs for interactive API docs.

Without SUPABASE_URL/SUPABASE_KEY set, community reports are stored in
memory (fine for local testing, resets on restart).

## Deploying to Render
1. Push this folder to a GitHub repo (can be the same repo as the
   frontend, or a separate one — either works).
2. On render.com: New → Web Service → connect the repo.
3. Build command: `pip install -r requirements.txt`
4. Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
5. Add environment variables: SUPABASE_URL, SUPABASE_KEY, FRONTEND_URL
   (your Vercel URL).
6. Once deployed, set VITE_API_URL in Vercel to this service's Render URL.

## Setting up Supabase
1. Create a project at supabase.com (free tier is enough).
2. Go to SQL Editor, paste and run `supabase_schema.sql`.
3. Go to Project Settings → API, copy the Project URL and the `anon`
   key into SUPABASE_URL / SUPABASE_KEY (in Render's env vars, and
   your local .env).

## Endpoints
- `POST /predict` — {origin, destination, mode, city, time?} → full prediction
- `POST /reports` — {city, type, location, timestamp?} → saves a community report
- `GET /reports?city=nairobi` — recent reports for a city
- `GET /health` — uptime check
