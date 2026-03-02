"use client";

import { useEffect, useMemo, useState } from "react";

import { GeoJSON, MapContainer, TileLayer } from "react-leaflet";

import { getNeighborhoods } from "@/lib/api";
import { NeighborhoodsResponse } from "@/lib/types";

type GenericGeoFeature = {
  type: "Feature";
  properties: Record<string, unknown>;
  geometry: unknown;
};

type GenericFeatureCollection = {
  type: "FeatureCollection";
  features: GenericGeoFeature[];
};

type EnrichedFeature = GenericGeoFeature & {
  properties: Record<string, unknown> & {
    __displayName: string;
    __meanCommuteMinutes: number | null;
  };
};

type EnrichedFeatureCollection = {
  type: "FeatureCollection";
  features: EnrichedFeature[];
};

const SF_BOUNDS: [[number, number], [number, number]] = [
  [37.7, -122.53],
  [37.84, -122.35],
];
const NAME_KEYS = [
  "name",
  "Name",
  "neighborhood",
  "Neighborhood",
  "neighborhood_name",
  "NeighborhoodName",
  "NHOOD",
  "nhood",
];

function normalizeNeighborhoodName(value: string): string {
  return value.trim().toLowerCase().replace(/\s+/g, " ");
}

function getNeighborhoodNameFromFeature(feature: GenericGeoFeature): string {
  for (const key of NAME_KEYS) {
    const value = feature.properties?.[key];
    if (typeof value === "string" && value.trim()) {
      return value.trim();
    }
  }

  for (const value of Object.values(feature.properties ?? {})) {
    if (typeof value === "string" && value.trim()) {
      return value.trim();
    }
  }

  return "Unknown";
}

function bucketColor(minutes: number | null): string {
  if (minutes === null || Number.isNaN(minutes)) return "#cbd5e1";
  if (minutes <= 30) return "#3ba559";
  if (minutes <= 40) return "#eab308";
  if (minutes <= 50) return "#f97316";
  return "#dc2626";
}

export default function NeighborhoodMapClient() {
  const [geoData, setGeoData] = useState<EnrichedFeatureCollection | null>(null);
  const [error, setError] = useState<string>("");

  useEffect(() => {
    let mounted = true;

    async function loadMapData() {
      setError("");

      try {
        const [baselineResponse, geoResponse] = await Promise.all([
          getNeighborhoods(),
          fetch("/neighborhoods.geojson", { cache: "force-cache" }),
        ]);

        if (!geoResponse.ok) {
          throw new Error("Failed to load neighborhood GeoJSON from /neighborhoods.geojson");
        }

        const rawGeoData = (await geoResponse.json()) as GenericFeatureCollection;
        const enriched = enrichGeoData(rawGeoData, baselineResponse);

        if (!mounted) return;
        setGeoData(enriched);
      } catch (err) {
        if (!mounted) return;
        setError(err instanceof Error ? err.message : "Failed to load map data");
      }
    }

    loadMapData();

    return () => {
      mounted = false;
    };
  }, []);

  const styledGeoJsonData = useMemo(() => geoData ?? null, [geoData]);

  return (
    <article className="rounded-2xl border border-black/10 bg-surface p-5 shadow-soft">
      <h2 className="text-xl font-semibold">Structural neighborhood heatmap</h2>
      <p className="mt-1 text-sm opacity-75">Color scale reflects mean commute minutes from ACS baseline data.</p>

      {error && <p className="mt-4 rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</p>}

      <div className="mt-4 min-h-[500px] overflow-hidden rounded-xl border border-black/10">
        {!styledGeoJsonData && !error ? (
          <div className="flex min-h-[500px] items-center justify-center text-sm opacity-75">Loading map...</div>
        ) : null}

        {styledGeoJsonData ? (
          <MapContainer bounds={SF_BOUNDS} className="h-[500px] w-full">
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />
            <GeoJSON
              data={styledGeoJsonData as any}
              style={(feature: any) => {
                const minutes = Number(feature?.properties?.__meanCommuteMinutes);
                const value = Number.isFinite(minutes) ? minutes : null;
                return {
                  fillColor: bucketColor(value),
                  fillOpacity: 0.6,
                  weight: 1,
                  color: "#333",
                };
              }}
              onEachFeature={(feature: any, layer: any) => {
                const name = String(feature.properties?.__displayName ?? "Unknown");
                const minutesRaw = Number(feature.properties?.__meanCommuteMinutes);
                const minutesLabel = Number.isFinite(minutesRaw) ? minutesRaw.toFixed(1) : "N/A";
                layer.bindTooltip(
                  `<strong>${name}</strong><br/>Mean Commute Minutes: ${minutesLabel}`,
                  {
                    sticky: true,
                  },
                );
              }}
            />
          </MapContainer>
        ) : null}
      </div>
    </article>
  );
}

function enrichGeoData(
  rawGeoData: GenericFeatureCollection,
  baselineResponse: NeighborhoodsResponse,
): EnrichedFeatureCollection {
  if (!rawGeoData || rawGeoData.type !== "FeatureCollection" || !Array.isArray(rawGeoData.features)) {
    throw new Error("GeoJSON data is not a valid FeatureCollection");
  }

  const backendLookup = new Map<string, { key: string; mean: number | null }>();
  for (const [name, details] of Object.entries(baselineResponse.data)) {
    const normalized = normalizeNeighborhoodName(name);
    backendLookup.set(normalized, {
      key: name,
      mean:
        typeof details.mean_commute_minutes === "number" && Number.isFinite(details.mean_commute_minutes)
          ? details.mean_commute_minutes
          : null,
    });
  }

  const matchedBackendKeys = new Set<string>();
  const unmatchedGeo: string[] = [];

  const features = rawGeoData.features.map((feature) => {
    const featureName = getNeighborhoodNameFromFeature(feature);
    const normalizedName = normalizeNeighborhoodName(featureName);
    const backendMatch = backendLookup.get(normalizedName);

    if (!backendMatch) {
      unmatchedGeo.push(featureName);
    } else {
      matchedBackendKeys.add(normalizedName);
    }

    return {
      ...feature,
      properties: {
        ...(feature.properties ?? {}),
        __displayName: backendMatch?.key ?? featureName,
        __meanCommuteMinutes: backendMatch?.mean ?? null,
      },
    };
  });

  const unmatchedBackend = Array.from(backendLookup.entries())
    .filter(([normalizedName]) => !matchedBackendKeys.has(normalizedName))
    .map(([, info]) => info.key);

  if (unmatchedGeo.length > 0) {
    console.warn("[NeighborhoodMap] Unmatched GeoJSON neighborhoods:", unmatchedGeo);
  }
  if (unmatchedBackend.length > 0) {
    console.warn("[NeighborhoodMap] Backend neighborhoods not present in GeoJSON:", unmatchedBackend);
  }

  return {
    type: "FeatureCollection",
    features,
  };
}
