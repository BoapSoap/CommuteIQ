# CommuteIQ Backend

FastAPI service for live commute friction and annual time/cost calculations.

## Run locally

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
uvicorn main:app --reload
```

API base URL: `http://localhost:8000`

One-command local bootstrap (venv + deps + ACS build + run API):

```bash
cd backend
./scripts/run_local.sh
```

## Required env

- `API_511_KEY`: your 511 API key (do not commit)
- `ALLOWED_ORIGINS`: comma-separated origins for CORS (default includes `http://localhost:3000`)
- `TRANSIT_AGENCIES` (optional): comma-separated 511 agency codes (default `BART,SFMTA`)
- `CACHE_TTL_SECONDS` (optional): live friction cache duration in seconds (default `600`)
- `CENSUS_API_KEY`: required for ACS preprocessing script
- `ACS_YEAR` (optional): ACS year used by preprocessing script (default `2023`)
- `AUTO_BUILD_ACS_ON_STARTUP` (optional): run ACS build on app startup (`false` by default)
- `ACS_BUILD_FORCE` (optional): when startup build is enabled, force rebuild even if JSON already exists (`false` by default)

## Endpoints

- `GET /health`
- `GET /friction/live`
- `GET /neighborhoods`
- `POST /calculate`

## Build ACS Neighborhood Baselines (offline)

Run manually from `backend/`:

```bash
python3 scripts/build_acs_neighborhoods.py
```

What it does:

- Fetches ACS tract-level data for San Francisco County (`state=06`, `county=075`)
- Downloads local TIGER tract geometry if missing
- Spatially joins tract centroids to `data/neighborhoods.geojson`
- Writes `data/acs_by_neighborhood.json`

This script is offline preprocessing only and is not executed by API endpoints.

If `AUTO_BUILD_ACS_ON_STARTUP=true`, the app can run this same build logic on startup.

## Render deploy

Start command:

```bash
uvicorn main:app --host 0.0.0.0 --port $PORT
```

Alternative script-based start:

```bash
./scripts/run_prod.sh
```
