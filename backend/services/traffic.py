from dataclasses import dataclass

import httpx

from .structural import Settings


TRAFFIC_EVENTS_URL = "https://api.511.org/traffic/events"
SEVERE_KEYWORDS = {
    "major",
    "sigalert",
    "severe",
    "حاد",
    "fatal",
    "closure",
    "full closure",
    "multi-vehicle",
}


@dataclass
class TrafficMetrics:
    incidents: int
    severe_incidents: int


def _is_severe(event: dict) -> bool:
    candidate_fields = [
        str(event.get("severity", "")),
        str(event.get("type", "")),
        str(event.get("event_type", "")),
        str(event.get("headline", "")),
        str(event.get("description", "")),
        str(event.get("status", "")),
    ]
    text = " ".join(candidate_fields).lower()
    return any(keyword in text for keyword in SEVERE_KEYWORDS)


def _extract_events(payload: object) -> list[dict]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]

    if not isinstance(payload, dict):
        return []

    for key in ("events", "incidents", "items", "results", "Features", "features"):
        value = payload.get(key)
        if isinstance(value, list):
            events: list[dict] = []
            for item in value:
                if not isinstance(item, dict):
                    continue
                # GeoJSON feature payloads carry event details in "properties".
                properties = item.get("properties")
                if isinstance(properties, dict):
                    events.append(properties)
                else:
                    events.append(item)
            return events

    return []


async def get_traffic_metrics(settings: Settings) -> TrafficMetrics:
    if not settings.api_511_key:
        return TrafficMetrics(incidents=0, severe_incidents=0)

    params = {"api_key": settings.api_511_key, "format": "json"}

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(TRAFFIC_EVENTS_URL, params=params, timeout=12.0)
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPError, ValueError):
        return TrafficMetrics(incidents=0, severe_incidents=0)

    events = _extract_events(payload)
    incidents = len(events)
    severe_incidents = sum(1 for event in events if _is_severe(event))

    return TrafficMetrics(incidents=incidents, severe_incidents=severe_incidents)
