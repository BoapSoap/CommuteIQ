import json
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


load_dotenv()

TRANSIT_AGENCY_ALIASES = {
    "SFMTA": "SF",
    "MUNI": "SF",
}


@dataclass(frozen=True)
class Settings:
    api_511_key: str
    openai_api_key: str
    allowed_origins: list[str]
    transit_agencies: list[str]
    cache_ttl_seconds: int
    auto_build_acs_on_startup: bool
    acs_build_force: bool
    data_path: Path


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _normalize_transit_agencies(agencies: list[str]) -> list[str]:
    normalized: list[str] = []
    for agency in agencies:
        code = TRANSIT_AGENCY_ALIASES.get(agency.strip().upper(), agency.strip().upper())
        if code and code not in normalized:
            normalized.append(code)
    return normalized


def _parse_bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name, str(default)).strip().lower()
    return raw in {"1", "true", "yes", "y", "on"}


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    allowed_origins = _split_csv(os.getenv("ALLOWED_ORIGINS", "http://localhost:3000"))
    transit_agencies = _normalize_transit_agencies(
        _split_csv(os.getenv("TRANSIT_AGENCIES", "BART,SFMTA"))
    )
    cache_ttl_seconds = int(os.getenv("CACHE_TTL_SECONDS", "600"))
    auto_build_acs_on_startup = _parse_bool_env("AUTO_BUILD_ACS_ON_STARTUP", False)
    acs_build_force = _parse_bool_env("ACS_BUILD_FORCE", False)
    data_path = Path(__file__).resolve().parent.parent / "data" / "acs_by_neighborhood.json"

    return Settings(
        api_511_key=os.getenv("API_511_KEY", ""),
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        allowed_origins=allowed_origins,
        transit_agencies=transit_agencies,
        cache_ttl_seconds=max(60, cache_ttl_seconds),
        auto_build_acs_on_startup=auto_build_acs_on_startup,
        acs_build_force=acs_build_force,
        data_path=data_path,
    )


@lru_cache(maxsize=1)
def load_neighborhood_baselines() -> dict[str, dict[str, Any]]:
    settings = get_settings()
    with settings.data_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        raise ValueError("Baseline neighborhood data must be an object")

    return data
