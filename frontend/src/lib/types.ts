export type Recommendation = "transit" | "driving";

export interface LiveFriction {
  transit: {
    score: number;
    delay_rate: number;
    avg_delay_minutes: number;
    alerts: number;
  };
  driving: {
    score: number;
    incidents: number;
    severe: number;
  };
  recommendation: Recommendation;
  last_updated: string;
  cache_ttl_seconds: number;
  agencies_used: string[];
  source: "511";
}

export interface ExplainLive {
  summary: string;
  last_updated: string;
  source: "openai" | "fallback";
}

export interface NeighborhoodsResponse {
  neighborhoods: string[];
  data: Record<
    string,
    {
      mean_commute_minutes?: number;
      transit_minutes: number;
      driving_minutes: number;
      median_income: number;
      vehicle_ownership_rate: number;
      mode_share?: {
        drive: number;
        transit: number;
        walk: number;
        bike: number;
        wfh: number;
      };
    }
  >;
}

export interface CalculateRequest {
  neighborhood: string;
  mode: Recommendation;
  trips_per_week: number;
  hourly_value: number;
}

export interface CalculateResponse {
  neighborhood: string;
  mode: Recommendation;
  friction_score: number;
  baseline_minutes: number;
  adjusted_minutes: number;
  baseline_annual_hours: number;
  adjusted_annual_hours: number;
  extra_hours: number;
  baseline_annual_cost: number;
  adjusted_annual_cost: number;
  extra_cost: number;
}
