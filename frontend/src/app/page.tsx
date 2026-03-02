"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";

import NeighborhoodMap from "@/components/NeighborhoodMap";
import { calculateCommute, getLiveExplanation, getLiveFriction, getNeighborhoods } from "@/lib/api";
import { CalculateResponse, ExplainLive, LiveFriction, Recommendation } from "@/lib/types";

export default function Home() {
  const [live, setLive] = useState<LiveFriction | null>(null);
  const [explanation, setExplanation] = useState<ExplainLive | null>(null);
  const [neighborhoods, setNeighborhoods] = useState<string[]>([]);
  const [calcResult, setCalcResult] = useState<CalculateResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isRefreshingLive, setIsRefreshingLive] = useState(false);
  const [error, setError] = useState<string>("");

  const [neighborhood, setNeighborhood] = useState("");
  const [mode, setMode] = useState<Recommendation>("transit");
  const [tripsPerWeek, setTripsPerWeek] = useState(10);
  const [hourlyValue, setHourlyValue] = useState(65);

  useEffect(() => {
    let mounted = true;

    async function bootstrap() {
      setError("");
      try {
        const [liveData, neighborhoodData, explanationData] = await Promise.all([
          getLiveFriction(),
          getNeighborhoods(),
          getLiveExplanation(),
        ]);

        if (!mounted) return;

        setLive(liveData);
        setNeighborhoods(neighborhoodData.neighborhoods);
        setExplanation(explanationData);
        setNeighborhood((prev) => prev || neighborhoodData.neighborhoods[0] || "");
      } catch (err) {
        if (!mounted) return;
        setError(err instanceof Error ? err.message : "Failed to load data");
      }
    }

    bootstrap();

    return () => {
      mounted = false;
    };
  }, []);

  const formattedUpdated = useMemo(() => {
    if (!live?.last_updated) return "-";
    return new Date(live.last_updated).toLocaleString();
  }, [live?.last_updated]);

  const formattedExplanationUpdated = useMemo(() => {
    if (!explanation?.last_updated) return "-";
    return new Date(explanation.last_updated).toLocaleString();
  }, [explanation?.last_updated]);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setIsLoading(true);

    try {
      const result = await calculateCommute({
        neighborhood,
        mode,
        trips_per_week: Number(tripsPerWeek),
        hourly_value: Number(hourlyValue),
      });
      setCalcResult(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Calculation failed");
    } finally {
      setIsLoading(false);
    }
  }

  async function onRefreshLive() {
    setError("");
    setIsRefreshingLive(true);
    try {
      const liveData = await getLiveFriction(true);
      setLive(liveData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Live refresh failed");
    } finally {
      setIsRefreshingLive(false);
    }
  }

  return (
    <main className="min-h-screen px-4 py-12 md:px-12">
      <div className="mx-auto max-w-5xl space-y-6">
        <header className="space-y-2">
          <div className="rounded-2xl border border-black/10 bg-[#102820] px-6 py-8 text-white shadow-soft md:px-10 md:py-10">
            <p className="text-5xl font-semibold tracking-tight md:text-7xl">CommuteIQ</p>
            <p className="mt-3 max-w-2xl text-sm text-white/85 md:text-base">
              San Francisco commute intelligence with live 511 transit and traffic signals plus a personal annual
              time-tax calculator.
            </p>
          </div>
        </header>

        {error && (
          <div className="rounded-xl border border-red-300 bg-red-50 p-3 text-sm text-red-700">
            {error}
          </div>
        )}

        <section className="grid gap-4 md:grid-cols-3">
          <article className="rounded-2xl border border-black/10 bg-surface p-5 shadow-soft md:col-span-2">
            <h2 className="text-xl font-semibold">Live status panel</h2>
            <p className="mt-1 text-sm opacity-70">Updated: {formattedUpdated}</p>
            <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="rounded-xl bg-[#e8f3ef] p-4">
                <p className="text-xs uppercase tracking-[0.12em] opacity-70">Transit friction</p>
                <p className="mt-1 text-3xl font-semibold">{live?.transit.score ?? "-"}</p>
                <p className="mt-2 text-sm">
                  Delay rate: {live?.transit.delay_rate ?? 0}% | Avg delay: {live?.transit.avg_delay_minutes ?? 0}m
                </p>
                <p className="text-sm">Alerts: {live?.transit.alerts ?? 0}</p>
              </div>
              <div className="rounded-xl bg-[#f6e8de] p-4">
                <p className="text-xs uppercase tracking-[0.12em] opacity-70">Driving friction</p>
                <p className="mt-1 text-3xl font-semibold">{live?.driving.score ?? "-"}</p>
                <p className="mt-2 text-sm">Incidents: {live?.driving.incidents ?? 0}</p>
                <p className="text-sm">Severe incidents: {live?.driving.severe ?? 0}</p>
              </div>
            </div>
            <p className="mt-4 text-sm">
              Recommended today: <span className="font-semibold uppercase">{live?.recommendation ?? "-"}</span>
            </p>
          </article>

          <article className="rounded-2xl border border-black/10 bg-accent p-5 text-white shadow-soft">
            <h2 className="text-lg font-semibold">Source</h2>
            <p className="mt-2 text-sm opacity-95">{live?.source ?? "511"} public APIs</p>
            <p className="mt-2 text-xs opacity-90">
              Agencies: {live?.agencies_used?.join(", ") || "BART, SFMTA"}
            </p>
            <p className="mt-1 text-xs opacity-90">
              Cache TTL: {live?.cache_ttl_seconds ?? 600}s (upstream only after expiry)
            </p>
            <button
              onClick={onRefreshLive}
              disabled={isRefreshingLive}
              className="mt-6 w-full rounded-lg border border-white/70 px-4 py-2 text-sm font-semibold transition hover:bg-white hover:text-accent"
            >
              {isRefreshingLive ? "Refreshing..." : "Refresh snapshot"}
            </button>
            <p className="mt-2 text-xs opacity-90">Manual refresh is limited to once every 5 minutes.</p>
          </article>
        </section>

        <section>
          <article className="rounded-2xl border border-black/10 bg-surface p-5 shadow-soft">
            <h2 className="text-xl font-semibold">AI Summary</h2>
            <p className="mt-1 text-sm opacity-70">Generated at: {formattedExplanationUpdated}</p>
            <p className="mt-4 text-sm leading-6">
              {explanation?.summary ?? "Loading AI summary..."}
            </p>
          </article>
        </section>

        <section className="grid gap-4 md:grid-cols-2">
          <article className="rounded-2xl border border-black/10 bg-surface p-5 shadow-soft">
            <h2 className="text-xl font-semibold">Personal calculator</h2>
            <form className="mt-4 space-y-3" onSubmit={onSubmit}>
              <label className="block text-sm">
                Neighborhood
                <select
                  className="mt-1 w-full rounded-lg border border-black/20 bg-white px-3 py-2"
                  value={neighborhood}
                  onChange={(e) => setNeighborhood(e.target.value)}
                  required
                >
                  {neighborhoods.map((option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ))}
                </select>
              </label>

              <label className="block text-sm">
                Mode
                <select
                  className="mt-1 w-full rounded-lg border border-black/20 bg-white px-3 py-2"
                  value={mode}
                  onChange={(e) => setMode(e.target.value as Recommendation)}
                >
                  <option value="transit">Transit</option>
                  <option value="driving">Driving</option>
                </select>
              </label>

              <label className="block text-sm">
                Trips per week
                <input
                  className="mt-1 w-full rounded-lg border border-black/20 bg-white px-3 py-2"
                  type="number"
                  min={1}
                  max={30}
                  value={tripsPerWeek}
                  onChange={(e) => setTripsPerWeek(Number(e.target.value))}
                  required
                />
              </label>

              <label className="block text-sm">
                Hourly value ($)
                <input
                  className="mt-1 w-full rounded-lg border border-black/20 bg-white px-3 py-2"
                  type="number"
                  min={1}
                  step={0.01}
                  value={hourlyValue}
                  onChange={(e) => setHourlyValue(Number(e.target.value))}
                  required
                />
              </label>

              <button
                className="w-full rounded-lg bg-foreground px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-60"
                type="submit"
                disabled={isLoading || !neighborhood}
              >
                {isLoading ? "Calculating..." : "Calculate annual impact"}
              </button>
            </form>
          </article>

          <article className="rounded-2xl border border-black/10 bg-surface p-5 shadow-soft">
            <h2 className="text-xl font-semibold">Results</h2>
            {!calcResult && <p className="mt-4 text-sm opacity-75">Run a calculation to see annual impact.</p>}

            {calcResult && (
              <div className="mt-4 space-y-3 text-sm">
                <div className="rounded-lg bg-[#f2f7f5] p-3">
                  <p>
                    Adjusted one-way commute: <span className="font-semibold">{calcResult.adjusted_minutes} min</span>
                  </p>
                  <p>Baseline one-way commute: {calcResult.baseline_minutes} min</p>
                  <p>Friction score used: {calcResult.friction_score}</p>
                </div>

                <div className="rounded-lg bg-[#f8f4ed] p-3">
                  <p>Baseline annual hours: {calcResult.baseline_annual_hours}</p>
                  <p>Adjusted annual hours: {calcResult.adjusted_annual_hours}</p>
                  <p className="font-semibold">Extra annual hours: {calcResult.extra_hours}</p>
                </div>

                <div className="rounded-lg bg-[#f0ebf7] p-3">
                  <p>Baseline annual cost: ${calcResult.baseline_annual_cost}</p>
                  <p>Adjusted annual cost: ${calcResult.adjusted_annual_cost}</p>
                  <p className="font-semibold">Extra annual cost: ${calcResult.extra_cost}</p>
                </div>
              </div>
            )}
          </article>
        </section>

        <section>
          <NeighborhoodMap />
        </section>
      </div>
    </main>
  );
}
