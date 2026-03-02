import {
  CalculateRequest,
  CalculateResponse,
  ExplainLive,
  LiveFriction,
  NeighborhoodsResponse,
} from "@/lib/types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

async function fetchJSON<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    ...init,
    cache: "no-store",
  });

  if (!response.ok) {
    const text = await response.text();
    let detail = "";
    try {
      const parsed = JSON.parse(text) as { detail?: string };
      detail = parsed?.detail ?? "";
    } catch {
      detail = "";
    }
    throw new Error(detail || text || `Request failed with status ${response.status}`);
  }

  return (await response.json()) as T;
}

export const getLiveFriction = (refresh = false) =>
  fetchJSON<LiveFriction>(refresh ? "/friction/live?refresh=true" : "/friction/live");

export const getLiveExplanation = () =>
  fetchJSON<ExplainLive>("/explain/live");

export const getNeighborhoods = () =>
  fetchJSON<NeighborhoodsResponse>("/neighborhoods");

export const calculateCommute = (payload: CalculateRequest) =>
  fetchJSON<CalculateResponse>("/calculate", {
    method: "POST",
    body: JSON.stringify(payload),
  });
