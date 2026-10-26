"use client";
import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import { api } from "@/lib/api";
import { useFilters } from "@/lib/filters";
import { fmtChange, fmtValue } from "@/lib/format";
import { useInvestigate, useSlice } from "@/lib/hooks";
import { RegionMap } from "@/components/map/RegionMap";
import { NativeSelect, Panel, Seg } from "./Panel";
import { DemoBadge } from "./Status";

export const MAP_METRICS = [
  { id: "claimant_rate", label: "Claimant count rate", unit: "%", lad: true, d: 1 },
  { id: "aps_unemployment_rate", label: "Unemployment rate (APS)", unit: "%", lad: true, d: 1 },
  { id: "aps_employment_rate", label: "Employment rate 16-64 (APS)", unit: "%", lad: true, d: 1 },
  { id: "ashe_weekly_pay_ft", label: "Median weekly pay, full-time", unit: "£", lad: true, d: 0 },
  { id: "hpi_avg_price", label: "Average house price", unit: "£", lad: false, d: 0 },
  { id: "hpi_yoy", label: "House price inflation", unit: "%", lad: false, d: 1 },
  { id: "business_counts", label: "Enterprises in selected sector", unit: "enterprises", lad: true, d: 0, dim: true },
];

export function useAreas() {
  return useQuery({
    queryKey: ["areas"],
    queryFn: () => api<{ code: string; name: string; level: string; parent: string | null }[]>("/geo/areas"),
    staleTime: Infinity,
  });
}

/** Regional choropleth with metric/level/period controls. Selecting an area sets the global geography filter. */
export function RegionMapPanel({ metric, setMetric, level, setLevel, height = 380, className, period, setPeriod }: {
  metric: string; setMetric: (m: string) => void; level: "itl1" | "lad"; setLevel: (l: "itl1" | "lad") => void;
  height?: number; className?: string; period?: string | null; setPeriod?: (p: string | null) => void;
}) {
  const { filters, set } = useFilters();
  const inv = useInvestigate();
  const m = MAP_METRICS.find((x) => x.id === metric) ?? MAP_METRICS[0];
  const effLevel = m.lad ? level : "itl1";
  const dim = m.dim ? (filters.sector ?? "C") : undefined;
  const { data, isLoading, error } = useSlice(m.id, { by: "geo", level: effLevel, dim, period });
  const { data: areas } = useAreas();
  const focus = useMemo(() => {
    if (effLevel !== "lad" || !filters.geo || !areas) return null;
    const kids = areas.filter((a) => a.parent === filters.geo).map((a) => a.code);
    return kids.length ? kids : null;
  }, [effLevel, filters.geo, areas]);
  const sel = data?.rows.find((r) => r.geo === filters.geo);
  return (
    <Panel
      title={`Regional map · ${m.label}${m.dim ? ` (SIC ${dim})` : ""}`}
      subtitle={data ? `${data.period ?? ""} · ${effLevel === "lad" ? "Local authorities" : "ITL1 regions & nations"} · click an area to filter all views` : undefined}
      className={className}
      loading={isLoading}
      error={(error as Error | null)?.message}
      demo={data?.data_status === "demo"}
      investigate={inv({ series: m.id, geo: filters.geo ?? undefined, dim, period: data?.period })}
      actions={<>
        {data?.data_status === "demo" && <DemoBadge />}
        <NativeSelect label="" value={m.id} onChange={setMetric}
          options={MAP_METRICS.map((x) => ({ value: x.id, label: x.label }))} />
        <Seg value={effLevel} onChange={setLevel} label="Level" options={[
          { value: "itl1", label: "Regions" },
          { value: "lad", label: "LAs", disabled: !m.lad, title: m.lad ? undefined : "Not published at LA level by this source" }]} />
        {setPeriod && data && data.periods.length > 1 && (
          <NativeSelect label="" value={data.period ?? ""} onChange={(v) => setPeriod(v)}
            options={[...data.periods].reverse().map((p) => ({ value: p, label: p }))} />
        )}
      </>}
    >
      <RegionMap
        level={effLevel}
        unit={m.unit}
        decimals={m.d}
        height={height}
        selected={filters.geo}
        focusCodes={focus}
        data={(data?.rows ?? []).map((r) => ({ code: r.geo, value: r.value }))}
        onSelect={(code) => set({ geo: filters.geo === code ? null : code })}
      />
      {sel && (
        <div className="mt-1.5 flex flex-wrap items-center gap-3 rounded border bg-secondary/60 px-2 py-1 text-[11px]">
          <b>{sel.geo_name}</b>
          <span className="tabular">{fmtValue(sel.value, m.unit, m.d, false)}</span>
          <span className="tabular text-muted-foreground">{fmtChange(sel.change, data?.change_unit ?? "%")} vs {data?.previous_period}</span>
          {typeof sel.flags?.ci95_pp === "number" && <span className="text-muted-foreground">95% CI ±{sel.flags.ci95_pp as number}pp</span>}
          {typeof sel.flags?.cv_pct === "number" && <span className="text-muted-foreground">CV {sel.flags.cv_pct as number}%</span>}
        </div>
      )}
    </Panel>
  );
}
