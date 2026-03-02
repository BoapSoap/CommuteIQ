import asyncio
import json
from typing import Any

try:
    from openai import OpenAI
except Exception:  # pragma: no cover - fallback path when dependency is missing
    OpenAI = None  # type: ignore[assignment]

from models.schemas import ExplainLiveResponse, LiveFrictionResponse

from .friction import get_live_friction
from .structural import Settings

MODEL_NAME = "gpt-4.1-mini"

_explain_lock = asyncio.Lock()
_cached_snapshot_key: str | None = None
_cached_response: ExplainLiveResponse | None = None

AGENCY_NAME_MAP = {
    "SF": "SFMTA/Muni",
    "SFMTA": "SFMTA/Muni",
    "MUNI": "SFMTA/Muni",
    "BART": "BART",
}


def _friendly_agencies(agencies_used: list[str]) -> str:
    normalized: list[str] = []
    for agency in agencies_used:
        label = AGENCY_NAME_MAP.get(agency.upper(), agency)
        if label not in normalized:
            normalized.append(label)

    if not normalized:
        return "BART + SFMTA/Muni"
    if len(normalized) == 1:
        return normalized[0]
    return " + ".join(normalized)


def _transit_condition(score: int) -> str:
    if score >= 80:
        return "Transit is under severe disruption"
    if score >= 60:
        return "Transit is experiencing heavy delays"
    if score >= 40:
        return "Transit has moderate delay pressure"
    return "Transit is relatively stable"


def _driving_condition(score: int) -> str:
    if score >= 80:
        return "Driving conditions are severely congested"
    if score >= 60:
        return "Driving conditions are heavily congested"
    if score >= 40:
        return "Driving conditions are moderately congested"
    return "Driving conditions are relatively manageable"


def _practical_suggestion(live: LiveFrictionResponse) -> str:
    transit_score = live.transit.score
    driving_score = live.driving.score

    if live.recommendation == "transit":
        if transit_score >= 60:
            return "If you ride transit, avoid transfer-heavy itineraries and budget about 12 extra minutes."
        return "If you ride transit, budget about 6 extra minutes for headway variability."

    if driving_score >= 60:
        return "If you drive, leave about 15 minutes earlier and avoid known bottleneck corridors."
    return "If you drive, budget about 8 extra minutes for incident spillover."


def _build_rule_based_summary(live: LiveFrictionResponse) -> str:
    transit_score = live.transit.score
    driving_score = live.driving.score
    agencies = _friendly_agencies(live.agencies_used)

    comparison = (
        f"{_transit_condition(transit_score)} across {agencies} "
        f"(transit friction {transit_score}, delay rate {live.transit.delay_rate:.1f}%, "
        f"avg delay {live.transit.avg_delay_minutes:.1f} min, alerts {live.transit.alerts}), "
        f"while {_driving_condition(driving_score)} "
        f"(driving friction {driving_score}, incidents {live.driving.incidents}, severe {live.driving.severe})."
    )

    if live.recommendation == "transit":
        rationale = (
            f"Transit is recommended because its friction score ({transit_score}) is lower than driving ({driving_score})."
        )
    else:
        rationale = (
            f"Driving is recommended because its friction score ({driving_score}) is lower than transit ({transit_score})."
        )

    suggestion = _practical_suggestion(live)
    return f"{comparison} {rationale} {suggestion}"


def _extract_response_text(response: Any) -> str:
    output_text = getattr(response, "output_text", None)
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()

    output = getattr(response, "output", None)
    if not isinstance(output, list):
        return ""

    text_parts: list[str] = []
    for item in output:
        item_type = getattr(item, "type", None) or (item.get("type") if isinstance(item, dict) else None)
        if item_type != "message":
            continue

        content = getattr(item, "content", None) or (item.get("content") if isinstance(item, dict) else None)
        if not isinstance(content, list):
            continue

        for part in content:
            part_type = getattr(part, "type", None) or (part.get("type") if isinstance(part, dict) else None)
            if part_type not in {"output_text", "text"}:
                continue
            text = getattr(part, "text", None) or (part.get("text") if isinstance(part, dict) else None)
            if isinstance(text, str) and text.strip():
                text_parts.append(text.strip())

    return " ".join(text_parts).strip()


def _generate_openai_summary(settings: Settings, live: LiveFrictionResponse) -> str:
    if OpenAI is None:
        raise RuntimeError("openai SDK is not installed")

    client = OpenAI(api_key=settings.openai_api_key)
    payload = {
        "transit": {
            "score": live.transit.score,
            "delay_rate": live.transit.delay_rate,
            "avg_delay_minutes": live.transit.avg_delay_minutes,
            "alerts": live.transit.alerts,
        },
        "driving": {
            "score": live.driving.score,
            "incidents": live.driving.incidents,
            "severe": live.driving.severe,
        },
        "recommendation": live.recommendation,
        "agencies_used": _friendly_agencies(live.agencies_used),
        "last_updated": live.last_updated.isoformat(),
    }

    response = client.responses.create(
        model=MODEL_NAME,
        input=[
            {
                "role": "system",
                "content": (
                    "You are a commute analyst for San Francisco. Return plain text only, 2-3 sentences max. "
                    "Compare transit vs driving, justify the recommendation with the provided scores, mention agencies "
                    "(BART and SFMTA/Muni), and include one practical commuter suggestion."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(payload),
            },
        ],
        max_output_tokens=160,
    )

    return _extract_response_text(response)


async def get_live_explanation(settings: Settings) -> ExplainLiveResponse:
    global _cached_snapshot_key, _cached_response

    live = await get_live_friction(settings)
    snapshot_key = live.last_updated.isoformat()

    if _cached_snapshot_key == snapshot_key and _cached_response is not None:
        return _cached_response

    async with _explain_lock:
        if _cached_snapshot_key == snapshot_key and _cached_response is not None:
            return _cached_response

        summary = ""
        source = "fallback"

        if settings.openai_api_key:
            try:
                summary = await asyncio.to_thread(_generate_openai_summary, settings, live)
                if summary:
                    source = "openai"
            except Exception:
                summary = ""

        if not summary:
            summary = _build_rule_based_summary(live)
            source = "fallback"

        response = ExplainLiveResponse(
            summary=summary,
            last_updated=live.last_updated,
            source=source,
        )
        _cached_snapshot_key = snapshot_key
        _cached_response = response
        return response
