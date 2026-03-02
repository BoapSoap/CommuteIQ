import asyncio
import logging
from dataclasses import dataclass

import httpx
from google.transit import gtfs_realtime_pb2

from .structural import Settings


TRIP_UPDATES_URL = "https://api.511.org/transit/tripupdates"
SERVICE_ALERTS_URL = "https://api.511.org/transit/servicealerts"
logger = logging.getLogger(__name__)


@dataclass
class TransitMetrics:
    percent_delayed: float
    avg_delay_minutes: float
    alert_count: int


async def _fetch_gtfs_feed(client: httpx.AsyncClient, url: str, params: dict[str, str]) -> gtfs_realtime_pb2.FeedMessage | None:
    response = await client.get(url, params=params, timeout=12.0)
    response.raise_for_status()

    feed = gtfs_realtime_pb2.FeedMessage()
    feed.ParseFromString(response.content)
    return feed


def _trip_delay_seconds(entity: gtfs_realtime_pb2.FeedEntity) -> int:
    if not entity.HasField("trip_update"):
        return 0

    max_delay = 0
    for stop_update in entity.trip_update.stop_time_update:
        if stop_update.HasField("arrival") and stop_update.arrival.HasField("delay"):
            max_delay = max(max_delay, int(stop_update.arrival.delay))
        if stop_update.HasField("departure") and stop_update.departure.HasField("delay"):
            max_delay = max(max_delay, int(stop_update.departure.delay))

    return max_delay


async def get_transit_metrics(settings: Settings) -> TransitMetrics:
    if not settings.api_511_key:
        return TransitMetrics(percent_delayed=0.0, avg_delay_minutes=0.0, alert_count=0)

    total_trips = 0
    delayed_trip_count = 0
    delayed_seconds_total = 0
    alert_count = 0

    async with httpx.AsyncClient() as client:
        tasks: list[asyncio.Task] = []

        for agency in settings.transit_agencies:
            trip_params = {"api_key": settings.api_511_key, "agency": agency}
            alert_params = {"api_key": settings.api_511_key, "agency": agency}

            tasks.append(asyncio.create_task(_fetch_gtfs_feed(client, TRIP_UPDATES_URL, trip_params)))
            tasks.append(asyncio.create_task(_fetch_gtfs_feed(client, SERVICE_ALERTS_URL, alert_params)))

        results = await asyncio.gather(*tasks, return_exceptions=True)

    for result in results:
        if isinstance(result, Exception) or result is None:
            if isinstance(result, Exception):
                logger.warning("Transit feed fetch failed: %s", result)
            continue

        has_trip_updates = any(entity.HasField("trip_update") for entity in result.entity)

        if has_trip_updates:
            for entity in result.entity:
                if not entity.HasField("trip_update"):
                    continue
                total_trips += 1
                delay_seconds = _trip_delay_seconds(entity)
                if delay_seconds > 0:
                    delayed_trip_count += 1
                    delayed_seconds_total += delay_seconds
        else:
            alert_count += sum(1 for entity in result.entity if entity.HasField("alert"))

    percent_delayed = (delayed_trip_count / total_trips * 100) if total_trips else 0.0
    avg_delay_minutes = (delayed_seconds_total / delayed_trip_count / 60) if delayed_trip_count else 0.0

    return TransitMetrics(
        percent_delayed=round(percent_delayed, 2),
        avg_delay_minutes=round(avg_delay_minutes, 2),
        alert_count=alert_count,
    )
