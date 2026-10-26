"use client";
import { useRouter } from "next/navigation";
import { useQueries } from "@tanstack/react-query";
import { api, qs, type ObservationsResponse } from "@/lib/api";
import { useFilters } from "@/lib/filters";
import { useInvestigate } from "@/lib/hooks";
import { obsTime } from "@/lib/format";
import { TimeSeriesChart, type TSSeries } from "@/components/charts/TimeSeriesChart";
import { Panel } from "./Panel";
import { DemoBadge } from "./Status";

/**
 * Panel plotting one or more catalogue series sharing a unit, respecting global date filters.
 * Clicking any point opens that exact observation in the investigation workspace.
 */
export function SeriesPanel({
  title, ids, unit, decimals = 1, kinds, height = 200, geo, dim, className, group, subtitle, defaultFrom, names,
}: {
  title: string;
  ids: string[];
  unit: string;
  decimals?: number;
  kinds?: ("line" | "bar" | "area")[];
  height?: number;
  geo?: string | null;
  dim?: string | null;
  className?: string;
  group?: string;
  subtitle?: string;
  defaultFrom?: string;
  names?: string[];
}) {
  const { filters } = useFilters();
  const router = useRouter();
  const inv = useInvestigate();
  const start = filters.from ?? defaultFrom ?? null;
  const results = useQueries({
    queries: ids.map((id) => ({
      queryKey: ["obs", id, { geo, dim, start, end: filters.to }],
      queryFn: () => api<ObservationsResponse>(`/series/${id}/observations${qs({ geo, dim, start, end: filters.to })}`),
    })),
  });
  const loading = results.some((r) => r.isLoading);
  const err = results.find((r) => r.error)?.error as Error | undefined;
  const demo = results.some((r) => r.data?.data_status === "demo");
  const series: TSSeries[] = results.filter((r) => r.data).map((r, i) => ({
      key: r.data!.series_id,
      name: names?.[i] ?? r.data!.title,
      kind: kinds?.[i] ?? "line",
      points: r.data!.observations.map((o) => ({ t: obsTime(o, r.data!.frequency), v: o.value, period: o.period })),
  }));
  const empty = !loading && series.every((s) => s.points.length === 0) ? "No observations retrieved yet" : null;
  const publishers = [...new Set(results.map((r) => r.data?.provenance.publisher).filter(Boolean))].join(", ");
  return (
    <Panel
      title={title}
      subtitle={subtitle ?? publishers}
      className={className}
      loading={loading}
      error={err?.message}
      empty={empty}
      demo={demo}
      investigate={ids[0] ? inv({ series: ids[0], geo, dim }) : undefined}
      actions={demo ? <DemoBadge /> : undefined}
    >
      <TimeSeriesChart
        series={series}
        unit={unit}
        decimals={decimals}
        height={height}
        group={group}
        onPointClick={(key, p) => router.push(inv({ series: key, geo, dim, period: p.period }))}
      />
    </Panel>
  );
}
