"use client";
import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { api } from "@/lib/api";
import { DIVERGING, INK } from "@/lib/colors";
import { useFilters } from "@/lib/filters";
import { fmtChange, fmtValue } from "@/lib/format";
import { useInvestigate } from "@/lib/hooks";
import { EChart } from "@/components/charts/EChart";
import { baseText, tooltipBase } from "@/components/charts/theme";
import { Panel, Seg } from "./Panel";
import { DemoBadge } from "./Status";

export interface HeatmapRow {
  series_id: string; section: string; name: string;
  cells: { period: string; value: number; level: number }[];
  workforce_jobs?: { value: number; period: string } | null;
  enterprises?: { value: number; period: string } | null;
}
export interface HeatmapResp {
  measure: string; periods: string[]; rows: HeatmapRow[]; data_status: "real" | "demo"; method: string; source: string;
}

export function useHeatmap(measure: string, months = 12) {
  return useQuery({
    queryKey: ["heatmap", measure, months],
    queryFn: () => api<HeatmapResp>(`/industry/heatmap?measure=${measure}&months=${months}`),
  });
}

/** Industries x months; diverging colour around 0 (red = contraction, blue = growth). Click a cell to investigate. */
export function IndustryHeatmap({ height = 340, months = 12, onSelectSector, className }: {
  height?: number; months?: number; onSelectSector?: (s: string) => void; className?: string;
}) {
  const [measure, setMeasure] = useState<"yoy" | "3m3m" | "mom">("yoy");
  const { data, isLoading, error } = useHeatmap(measure, months);
  const { filters } = useFilters();
  const router = useRouter();
  const inv = useInvestigate();
  const option = useMemo(() => {
    if (!data) return {};
    const rows = [...data.rows].reverse();
    const cells: [number, number, number | null][] = [];
    rows.forEach((r, yi) => r.cells.forEach((c) => {
      const xi = data.periods.indexOf(c.period);
      if (xi >= 0) cells.push([xi, yi, Number(c.value.toFixed(2))]);
    }));
    const max = Math.max(1, ...cells.map((c) => Math.abs(c[2] ?? 0)));
    const lim = Math.min(Math.ceil(max), measure === "mom" ? 5 : 15);
    return {
      animation: false,
      grid: { left: 4, right: 8, top: 4, bottom: 46, containLabel: true },
      tooltip: {
        ...tooltipBase,
        formatter: (p: { data: [number, number, number] }) => {
          const r = rows[p.data[1]];
          const c = r.cells.find((x) => x.period === data.periods[p.data[0]]);
          return `<div style="font-size:11px"><b>${r.section}: ${r.name}</b><br/>${data.periods[p.data[0]]}<br/>
            ${fmtChange(p.data[2], "%")} (${measure === "yoy" ? "y/y" : measure === "mom" ? "m/m" : "3m/3m"})<br/>
            <span style="color:${INK.muted}">Index level ${fmtValue(c?.level, "index", 1)}</span><br/>
            <span style="color:${INK.muted};font-size:10px">Click to investigate</span></div>`;
        },
      },
      xAxis: { type: "category", data: data.periods, axisLabel: { ...baseText, interval: 1 }, axisLine: { show: false },
        axisTick: { show: false }, splitArea: { show: false } },
      yAxis: { type: "category", data: rows.map((r) => `${r.section} ${r.name.length > 26 ? r.name.slice(0, 25) + "…" : r.name}`),
        axisLabel: { ...baseText, color: INK.secondary,
          formatter: (v: string) => (filters.sector && v.startsWith(filters.sector + " ") ? `{sel|${v}}` : v),
          rich: { sel: { color: "#e8a33d", fontWeight: "bold", fontSize: 10 } } },
        axisLine: { show: false }, axisTick: { show: false } },
      visualMap: { min: -lim, max: lim, calculable: false, orient: "horizontal", left: "center", bottom: 0,
        itemHeight: 140, itemWidth: 8, text: [`+${lim}%`, `−${lim}%`], textStyle: baseText,
        inRange: { color: [DIVERGING.neg, DIVERGING.mid, DIVERGING.pos] } },
      series: [{ type: "heatmap", data: cells, itemStyle: { borderColor: INK.surface, borderWidth: 2, borderRadius: 2 },
        emphasis: { itemStyle: { borderColor: "#e8a33d", borderWidth: 1 } } }],
    };
  }, [data, measure, filters.sector]);
  const sel = data?.rows.find((r) => r.section === filters.sector);
  return (
    <Panel
      title="Industry heatmap · output growth by SIC 2007 section"
      subtitle={data ? `${data.source}. ${data.method}.` : "ONS monthly GDP"}
      className={className}
      loading={isLoading}
      error={(error as Error | null)?.message}
      demo={data?.data_status === "demo"}
      investigate={sel ? inv({ series: sel.series_id }) : undefined}
      actions={<>
        {data?.data_status === "demo" && <DemoBadge />}
        <Seg value={measure} onChange={setMeasure} label="Measure" options={[
          { value: "yoy", label: "y/y" }, { value: "3m3m", label: "3m/3m" }, { value: "mom", label: "m/m" }]} />
      </>}
    >
      <EChart option={option} height={height} ariaLabel="Heatmap of output growth by industry and month"
        onClick={(p) => {
          const d = p.data as [number, number, number] | undefined;
          if (!d || !data) return;
          const rows = [...data.rows].reverse();
          const r = rows[d[1]];
          if (onSelectSector) onSelectSector(r.section);
          else router.push(inv({ series: r.series_id, period: data.periods[d[0]] }));
        }} />
    </Panel>
  );
}
