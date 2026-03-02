#!/usr/bin/env python3
"""Build neighborhood-level ACS baselines for CommuteIQ.

This is an offline preprocessing step. It fetches ACS tract-level data,
joins tract centroids to SF neighborhood polygons, and writes
`backend/data/acs_by_neighborhood.json`.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import geopandas as gpd
import pandas as pd
import requests
from dotenv import load_dotenv
from shapely.geometry import Point

STATE_FIPS = "06"
COUNTY_FIPS = "075"

PROFILE_DATASET = "acs/acs5/profile"
SUBJECT_DATASET = "acs/acs5"

COMMUTE_VAR = "DP03_0025E"
INCOME_VAR = "B19013_001E"

MODE_VARS = [
    "B08301_001E",  # total workers
    "B08301_003E",  # drove alone
    "B08301_004E",  # carpooled
    "B08301_010E",  # public transit
    "B08301_018E",  # bicycle
    "B08301_019E",  # walked
    "B08301_021E",  # worked from home
]

VEHICLE_VARS = [
    "B25044_001E",  # total occupied housing units
    "B25044_003E",  # owner occupied, no vehicle
    "B25044_010E",  # renter occupied, no vehicle
]

NAME_CANDIDATE_COLUMNS = [
    "neighborhood",
    "Neighborhood",
    "name",
    "Name",
    "NHOOD",
    "nhood",
    "neighborhood_name",
    "NeighborhoodName",
]

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
DATA_DIR = BACKEND_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
TRACT_ZIP_NAME_TEMPLATE = "tl_{year}_06_tract.zip"
TRACT_URL_TEMPLATE = "https://www2.census.gov/geo/tiger/TIGER{year}/TRACT/tl_{year}_06_tract.zip"
NEIGHBORHOODS_PATH = DATA_DIR / "neighborhoods.geojson"
OUTPUT_PATH = DATA_DIR / "acs_by_neighborhood.json"
DOTENV_PATH = BACKEND_DIR / ".env"


def _require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(
            f"Missing required environment variable: {name}. "
            "Set it in backend/.env or your shell before running this script."
        )
    return value


def _parse_int_env(name: str, default: int) -> int:
    raw = os.environ.get(name, str(default)).strip()
    try:
        return int(raw)
    except ValueError as exc:
        raise RuntimeError(f"Environment variable {name} must be an integer, got: {raw}") from exc


def _census_request(session: requests.Session, year: int, dataset: str, get_clause: str, api_key: str) -> pd.DataFrame:
    url = f"https://api.census.gov/data/{year}/{dataset}"
    params = {
        "get": get_clause,
        "for": "tract:*",
        "in": f"state:{STATE_FIPS} county:{COUNTY_FIPS}",
        "key": api_key,
    }

    try:
        response = session.get(url, params=params, timeout=45)
        response.raise_for_status()
        rows = response.json()
    except requests.RequestException as exc:
        raise RuntimeError(f"Failed Census API request for dataset '{dataset}'.") from exc
    except ValueError as exc:
        raise RuntimeError(f"Invalid JSON response from Census API for dataset '{dataset}'.") from exc

    if not rows or len(rows) < 2:
        raise RuntimeError(f"No tract rows returned for dataset '{dataset}'.")

    header, *values = rows
    df = pd.DataFrame(values, columns=header)
    if not {"state", "county", "tract"}.issubset(df.columns):
        raise RuntimeError(f"Census response missing tract keys for dataset '{dataset}'.")

    df["GEOID"] = df["state"].astype(str) + df["county"].astype(str) + df["tract"].astype(str)
    return df


def _coerce_numeric(df: pd.DataFrame) -> pd.DataFrame:
    non_numeric = {"NAME", "state", "county", "tract", "GEOID"}
    for column in df.columns:
        if column in non_numeric:
            continue
        df[column] = pd.to_numeric(df[column], errors="coerce")
    return df


def _fetch_acs_frames(api_key: str, year: int) -> pd.DataFrame:
    with requests.Session() as session:
        commute_df = _census_request(
            session=session,
            year=year,
            dataset=PROFILE_DATASET,
            get_clause=f"NAME,{COMMUTE_VAR}",
            api_key=api_key,
        )
        income_df = _census_request(
            session=session,
            year=year,
            dataset=SUBJECT_DATASET,
            get_clause=f"NAME,{INCOME_VAR}",
            api_key=api_key,
        )
        mode_df = _census_request(
            session=session,
            year=year,
            dataset=SUBJECT_DATASET,
            get_clause="NAME,group(B08301)",
            api_key=api_key,
        )
        vehicle_df = _census_request(
            session=session,
            year=year,
            dataset=SUBJECT_DATASET,
            get_clause="NAME,group(B25044)",
            api_key=api_key,
        )

    commute_df = _coerce_numeric(commute_df[["GEOID", COMMUTE_VAR]])
    income_df = _coerce_numeric(income_df[["GEOID", INCOME_VAR]])

    mode_columns = ["GEOID"] + [col for col in MODE_VARS if col in mode_df.columns]
    vehicle_columns = ["GEOID"] + [col for col in VEHICLE_VARS if col in vehicle_df.columns]

    mode_df = _coerce_numeric(mode_df[mode_columns])
    vehicle_df = _coerce_numeric(vehicle_df[vehicle_columns])

    missing_mode_vars = [col for col in MODE_VARS if col not in mode_df.columns]
    if missing_mode_vars:
        raise RuntimeError(f"Missing expected B08301 columns: {', '.join(missing_mode_vars)}")

    missing_vehicle_vars = [col for col in VEHICLE_VARS if col not in vehicle_df.columns]
    if missing_vehicle_vars:
        raise RuntimeError(f"Missing expected B25044 columns: {', '.join(missing_vehicle_vars)}")

    merged = commute_df.merge(income_df, on="GEOID", how="inner")
    merged = merged.merge(mode_df, on="GEOID", how="inner")
    merged = merged.merge(vehicle_df, on="GEOID", how="inner")

    if merged.empty:
        raise RuntimeError("Merged ACS tract data is empty.")

    return merged


def _ensure_tiger_tract_zip(year: int) -> Path:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = RAW_DIR / TRACT_ZIP_NAME_TEMPLATE.format(year=year)
    if zip_path.exists():
        return zip_path

    url = TRACT_URL_TEMPLATE.format(year=year)
    try:
        with requests.get(url, stream=True, timeout=90) as response:
            response.raise_for_status()
            with zip_path.open("wb") as fh:
                for chunk in response.iter_content(chunk_size=1024 * 64):
                    if chunk:
                        fh.write(chunk)
    except requests.RequestException as exc:
        raise RuntimeError("Failed to download TIGER tract shapefile for California.") from exc

    return zip_path


def _detect_neighborhood_name_column(gdf: gpd.GeoDataFrame) -> str:
    for candidate in NAME_CANDIDATE_COLUMNS:
        if candidate in gdf.columns:
            return candidate

    for column in gdf.columns:
        if column == "geometry":
            continue
        if gdf[column].dtype == "object":
            return column

    raise RuntimeError("Could not find a neighborhood name column in neighborhoods.geojson")


def _load_spatial_join(year: int) -> pd.DataFrame:
    if not NEIGHBORHOODS_PATH.exists():
        raise RuntimeError(
            f"Missing neighborhood boundaries file: {NEIGHBORHOODS_PATH}. "
            "Add backend/data/neighborhoods.geojson before running this script."
        )

    tract_zip = _ensure_tiger_tract_zip(year)
    tracts = gpd.read_file(f"zip://{tract_zip}")
    tracts = tracts[tracts["COUNTYFP"] == COUNTY_FIPS].copy()
    if tracts.empty:
        raise RuntimeError("No tract geometries found for San Francisco County in TIGER data.")

    if "GEOID" not in tracts.columns:
        raise RuntimeError("Tract geometry data missing GEOID column.")

    neighborhoods = gpd.read_file(NEIGHBORHOODS_PATH)
    if neighborhoods.empty:
        raise RuntimeError("Neighborhood boundary GeoJSON is empty.")

    name_col = _detect_neighborhood_name_column(neighborhoods)

    if neighborhoods.crs is None:
        neighborhoods = neighborhoods.set_crs(epsg=4326)
    if tracts.crs is None:
        tracts = tracts.set_crs(epsg=4269)

    tracts = tracts.to_crs(neighborhoods.crs)

    centroids_projected = tracts.to_crs(epsg=3310).copy()
    centroids_projected["geometry"] = centroids_projected.geometry.centroid
    centroids = centroids_projected.to_crs(neighborhoods.crs)

    joined = gpd.sjoin(
        centroids[["GEOID", "geometry"]],
        neighborhoods[[name_col, "geometry"]],
        how="left",
        predicate="within",
    )

    missing_mask = joined[name_col].isna()
    if missing_mask.any():
        nearest = gpd.sjoin_nearest(
            centroids.loc[missing_mask, ["GEOID", "geometry"]],
            neighborhoods[[name_col, "geometry"]],
            how="left",
            distance_col="_dist",
        )
        nearest_map = nearest.set_index("GEOID")[name_col]
        joined.loc[missing_mask, name_col] = joined.loc[missing_mask, "GEOID"].map(nearest_map)

    # Touch shapely to make dependency explicit and validated at runtime.
    _ = Point(0, 0)

    return (
        joined[["GEOID", name_col]]
        .rename(columns={name_col: "neighborhood"})
        .dropna(subset=["neighborhood"])
        .drop_duplicates(subset=["GEOID"])
    )


def _safe_series(df: pd.DataFrame, column: str) -> pd.Series:
    if column in df.columns:
        return df[column].fillna(0)
    return pd.Series([0] * len(df), index=df.index, dtype="float64")


def _weighted_mean(values: pd.Series, weights: pd.Series) -> float:
    values = values.fillna(0)
    weights = weights.fillna(0)
    total_weight = float(weights.sum())
    if total_weight <= 0:
        if len(values) == 0:
            return 0.0
        return float(values.mean())
    return float((values * weights).sum() / total_weight)


def _build_neighborhood_json(merged: pd.DataFrame) -> dict[str, Any]:
    merged = merged.copy()

    workers_total = _safe_series(merged, "B08301_001E")
    merged["workers_total"] = workers_total.clip(lower=0)

    merged["drive_count"] = (_safe_series(merged, "B08301_003E") + _safe_series(merged, "B08301_004E")).clip(lower=0)
    merged["transit_count"] = _safe_series(merged, "B08301_010E").clip(lower=0)
    merged["walk_count"] = _safe_series(merged, "B08301_019E").clip(lower=0)
    merged["bike_count"] = _safe_series(merged, "B08301_018E").clip(lower=0)
    merged["wfh_count"] = _safe_series(merged, "B08301_021E").clip(lower=0)

    merged["households_total"] = _safe_series(merged, "B25044_001E").clip(lower=0)
    merged["no_vehicle_count"] = (
        _safe_series(merged, "B25044_003E") + _safe_series(merged, "B25044_010E")
    ).clip(lower=0)

    output: dict[str, Any] = {}

    for neighborhood, frame in merged.groupby("neighborhood", sort=True):
        workers = float(frame["workers_total"].sum())
        households = float(frame["households_total"].sum())

        mean_commute = _weighted_mean(frame[COMMUTE_VAR], frame["workers_total"])
        median_income = _weighted_mean(frame[INCOME_VAR], frame["households_total"])

        drive = float(frame["drive_count"].sum())
        transit = float(frame["transit_count"].sum())
        walk = float(frame["walk_count"].sum())
        bike = float(frame["bike_count"].sum())
        wfh = float(frame["wfh_count"].sum())

        if workers > 0:
            drive_share = drive / workers
            transit_share = transit / workers
            walk_share = walk / workers
            bike_share = bike / workers
            wfh_share = wfh / workers
        else:
            drive_share = 0.0
            transit_share = 0.0
            walk_share = 0.0
            bike_share = 0.0
            wfh_share = 0.0

        no_vehicle = float(frame["no_vehicle_count"].sum())
        vehicle_ownership_rate = ((households - no_vehicle) / households) if households > 0 else 0.0

        output[str(neighborhood)] = {
            "mean_commute_minutes": round(max(0.0, mean_commute), 2),
            "driving_minutes": round(max(0.0, mean_commute * 0.9), 2),
            "transit_minutes": round(max(0.0, mean_commute * 1.1), 2),
            "median_income": int(round(max(0.0, median_income))),
            "vehicle_ownership_rate": round(min(max(vehicle_ownership_rate, 0.0), 1.0), 4),
            "mode_share": {
                "drive": round(min(max(drive_share, 0.0), 1.0), 4),
                "transit": round(min(max(transit_share, 0.0), 1.0), 4),
                "walk": round(min(max(walk_share, 0.0), 1.0), 4),
                "bike": round(min(max(bike_share, 0.0), 1.0), 4),
                "wfh": round(min(max(wfh_share, 0.0), 1.0), 4),
            },
        }

    if not output:
        raise RuntimeError("No neighborhood aggregates were produced from tract data.")

    return output


def main() -> None:
    load_dotenv(DOTENV_PATH)

    api_key = _require_env("CENSUS_API_KEY")
    year = _parse_int_env("ACS_YEAR", 2023)

    acs_df = _fetch_acs_frames(api_key=api_key, year=year)
    geo_lookup = _load_spatial_join(year=year)

    merged = acs_df.merge(geo_lookup, on="GEOID", how="inner")
    merged = merged.dropna(subset=["neighborhood"]).copy()
    if merged.empty:
        raise RuntimeError("No tract rows matched to neighborhood geometries.")

    output = _build_neighborhood_json(merged)
    OUTPUT_PATH.write_text(json.dumps(output, indent=2), encoding="utf-8")

    print(f"Wrote neighborhood ACS baselines: {OUTPUT_PATH}")
    print(f"Neighborhoods aggregated: {len(output)}")


if __name__ == "__main__":
    main()
