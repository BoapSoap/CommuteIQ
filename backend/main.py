from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from models.schemas import (
    CalculateRequest,
    CalculateResponse,
    ExplainLiveResponse,
    HealthResponse,
    LiveFrictionResponse,
    NeighborhoodsResponse,
)
from services.acs_startup import maybe_build_acs_on_startup
from services.explain import get_live_explanation
from services.friction import RefreshTooSoonError, get_live_friction
from services.structural import get_settings, load_neighborhood_baselines


app = FastAPI(title="CommuteIQ API", version="0.1.0")
settings = get_settings()

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup() -> None:
    built = maybe_build_acs_on_startup(settings)
    if built:
        load_neighborhood_baselines.cache_clear()


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.get("/friction/live", response_model=LiveFrictionResponse)
async def friction_live(refresh: bool = False) -> LiveFrictionResponse:
    try:
        return await get_live_friction(settings, force_refresh=refresh)
    except RefreshTooSoonError as exc:
        wait_minutes = max(1, round(exc.wait_seconds / 60))
        raise HTTPException(
            status_code=429,
            detail=f"Please wait about {wait_minutes} minute(s) before refreshing again.",
        ) from exc


@app.get("/explain/live", response_model=ExplainLiveResponse)
async def explain_live() -> ExplainLiveResponse:
    return await get_live_explanation(settings)


@app.get("/neighborhoods", response_model=NeighborhoodsResponse)
async def neighborhoods() -> NeighborhoodsResponse:
    data = load_neighborhood_baselines()
    return NeighborhoodsResponse(neighborhoods=sorted(data.keys()), data=data)


def _round2(value: float) -> float:
    return round(value, 2)


@app.post("/calculate", response_model=CalculateResponse)
async def calculate(payload: CalculateRequest) -> CalculateResponse:
    neighborhoods_data = load_neighborhood_baselines()

    neighborhood = neighborhoods_data.get(payload.neighborhood)
    if not neighborhood:
        raise HTTPException(status_code=404, detail="Neighborhood not found")

    baseline_key = f"{payload.mode}_minutes"
    if baseline_key not in neighborhood:
        raise HTTPException(status_code=400, detail=f"Missing {baseline_key} in baseline data")

    live = await get_live_friction(settings)
    friction_score = live.transit.score if payload.mode == "transit" else live.driving.score

    baseline_minutes = float(neighborhood[baseline_key])
    adjusted_minutes = baseline_minutes * (1 + (friction_score / 100) * 0.5)

    baseline_annual_hours = (baseline_minutes * payload.trips_per_week * 50) / 60
    adjusted_annual_hours = (adjusted_minutes * payload.trips_per_week * 50) / 60
    extra_hours = adjusted_annual_hours - baseline_annual_hours

    baseline_annual_cost = baseline_annual_hours * payload.hourly_value
    adjusted_annual_cost = adjusted_annual_hours * payload.hourly_value
    extra_cost = adjusted_annual_cost - baseline_annual_cost

    return CalculateResponse(
        neighborhood=payload.neighborhood,
        mode=payload.mode,
        friction_score=friction_score,
        baseline_minutes=_round2(baseline_minutes),
        adjusted_minutes=_round2(adjusted_minutes),
        baseline_annual_hours=_round2(baseline_annual_hours),
        adjusted_annual_hours=_round2(adjusted_annual_hours),
        extra_hours=_round2(extra_hours),
        baseline_annual_cost=_round2(baseline_annual_cost),
        adjusted_annual_cost=_round2(adjusted_annual_cost),
        extra_cost=_round2(extra_cost),
    )
