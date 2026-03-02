import asyncio
import time
from datetime import datetime, timezone

from models.schemas import DrivingLiveStats, LiveFrictionResponse, TransitLiveStats

from .structural import Settings
from .traffic import get_traffic_metrics
from .transit import get_transit_metrics


FORCE_REFRESH_COOLDOWN_SECONDS = 300
_cache_lock = asyncio.Lock()
_cache_payload: LiveFrictionResponse | None = None
_cache_expiry_epoch = 0.0
_last_upstream_fetch_epoch = 0.0


class RefreshTooSoonError(Exception):
    def __init__(self, wait_seconds: int):
        self.wait_seconds = wait_seconds
        super().__init__(f"Wait {wait_seconds} seconds before refreshing again.")


def _clamp_score(value: float) -> int:
    value = max(0.0, min(100.0, value))
    return int(round(value))


def _compute_transit_score(percent_delayed: float, avg_delay_minutes: float, alert_count: int) -> int:
    delay_rate_score = min(percent_delayed / 50, 1)
    avg_delay_score = min(avg_delay_minutes / 20, 1)
    alert_score = min(alert_count / 20, 1)

    return _clamp_score(40 * delay_rate_score + 40 * avg_delay_score + 20 * alert_score)


def _compute_driving_score(incident_count: int, severe_incidents: int) -> int:
    incident_score = min(incident_count / 50, 1)
    severe_score = min(severe_incidents / 15, 1)

    return _clamp_score(60 * incident_score + 40 * severe_score)


async def build_live_friction(settings: Settings) -> LiveFrictionResponse:
    transit_metrics, traffic_metrics = await asyncio.gather(
        get_transit_metrics(settings),
        get_traffic_metrics(settings),
    )

    transit_score = _compute_transit_score(
        percent_delayed=transit_metrics.percent_delayed,
        avg_delay_minutes=transit_metrics.avg_delay_minutes,
        alert_count=transit_metrics.alert_count,
    )
    driving_score = _compute_driving_score(
        incident_count=traffic_metrics.incidents,
        severe_incidents=traffic_metrics.severe_incidents,
    )

    recommendation = "transit" if transit_score < driving_score else "driving"

    return LiveFrictionResponse(
        transit=TransitLiveStats(
            score=transit_score,
            delay_rate=transit_metrics.percent_delayed,
            avg_delay_minutes=transit_metrics.avg_delay_minutes,
            alerts=transit_metrics.alert_count,
        ),
        driving=DrivingLiveStats(
            score=driving_score,
            incidents=traffic_metrics.incidents,
            severe=traffic_metrics.severe_incidents,
        ),
        recommendation=recommendation,
        last_updated=datetime.now(timezone.utc),
        cache_ttl_seconds=settings.cache_ttl_seconds,
        agencies_used=settings.transit_agencies,
        source="511",
    )


async def get_live_friction(settings: Settings, force_refresh: bool = False) -> LiveFrictionResponse:
    global _cache_payload, _cache_expiry_epoch, _last_upstream_fetch_epoch

    now = time.time()
    if force_refresh and _last_upstream_fetch_epoch > 0:
        elapsed = now - _last_upstream_fetch_epoch
        if elapsed < FORCE_REFRESH_COOLDOWN_SECONDS:
            raise RefreshTooSoonError(wait_seconds=int(FORCE_REFRESH_COOLDOWN_SECONDS - elapsed))
    if _cache_payload and now < _cache_expiry_epoch:
        return _cache_payload

    async with _cache_lock:
        now = time.time()
        if force_refresh and _last_upstream_fetch_epoch > 0:
            elapsed = now - _last_upstream_fetch_epoch
            if elapsed < FORCE_REFRESH_COOLDOWN_SECONDS:
                raise RefreshTooSoonError(wait_seconds=int(FORCE_REFRESH_COOLDOWN_SECONDS - elapsed))
        if _cache_payload and now < _cache_expiry_epoch:
            return _cache_payload

        payload = await build_live_friction(settings)
        _cache_payload = payload
        _last_upstream_fetch_epoch = now
        _cache_expiry_epoch = now + settings.cache_ttl_seconds
        return payload
