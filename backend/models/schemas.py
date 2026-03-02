from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: Literal["ok"]


class TransitLiveStats(BaseModel):
    score: int = Field(ge=0, le=100)
    delay_rate: float = Field(ge=0)
    avg_delay_minutes: float = Field(ge=0)
    alerts: int = Field(ge=0)


class DrivingLiveStats(BaseModel):
    score: int = Field(ge=0, le=100)
    incidents: int = Field(ge=0)
    severe: int = Field(ge=0)


class LiveFrictionResponse(BaseModel):
    transit: TransitLiveStats
    driving: DrivingLiveStats
    recommendation: Literal["transit", "driving"]
    last_updated: datetime
    cache_ttl_seconds: int = Field(ge=1)
    agencies_used: list[str]
    source: Literal["511"]


class CalculateRequest(BaseModel):
    neighborhood: str
    mode: Literal["transit", "driving"]
    trips_per_week: int = Field(gt=0, le=30)
    hourly_value: float = Field(gt=0)


class CalculateResponse(BaseModel):
    neighborhood: str
    mode: Literal["transit", "driving"]
    friction_score: int = Field(ge=0, le=100)

    baseline_minutes: float
    adjusted_minutes: float

    baseline_annual_hours: float
    adjusted_annual_hours: float
    extra_hours: float

    baseline_annual_cost: float
    adjusted_annual_cost: float
    extra_cost: float


class ModeShare(BaseModel):
    drive: float = Field(ge=0, le=1)
    transit: float = Field(ge=0, le=1)
    walk: float = Field(ge=0, le=1)
    bike: float = Field(ge=0, le=1)
    wfh: float = Field(ge=0, le=1)


class NeighborhoodStat(BaseModel):
    mean_commute_minutes: float | None = None
    transit_minutes: float
    driving_minutes: float
    median_income: float
    vehicle_ownership_rate: float
    mode_share: ModeShare | None = None


class NeighborhoodsResponse(BaseModel):
    neighborhoods: list[str]
    data: dict[str, NeighborhoodStat]


class ExplainLiveResponse(BaseModel):
    summary: str
    last_updated: datetime
    source: Literal["openai", "fallback"]
