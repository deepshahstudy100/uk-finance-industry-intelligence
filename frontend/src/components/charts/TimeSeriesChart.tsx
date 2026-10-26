"use client";
import { useMemo } from "react";
import { INK, seriesColor } from "@/lib/colors";
import { fmtValue } from "@/lib/format";
import { EChart } from "./EChart";
import { axisTime, axisValue, gridBase, legendBase, tooltipBase } from "./theme";

export interface TSPoint { t: string; v: number | null; period?: string | null }
export interface TSSeries {
  key: string;
  name: string;
  points: TSPoint[];
  kind?: "line" | "bar" | "area";
  dashed?: boolean;
  colorIndex?: number;
  stack?: string;
}

/**
 * One value axis only (never dual-axis): all series must share `unit`. Callers with mixed units index them
 * or use small multiples. Clicking a point reports (seriesKey, point) so the caller can open the workspace.
 */
export function TimeSeriesChart({
  series, unit, decimals = 1, height = 220, onPointClick, group, zoom = false, markers, selected, baseline,
  showLegend, yMin, yMax,
}: {
  series: TSSeries[];
  unit: string;
  decimals?: number;
  height?: number;
  onPointClick?: (key: string, p: TSPoint) => void;
  group?: string;
  zoom?: boolean;
  markers?: { t: string; label: string }[];
  selected?: string | null;
  baseline?: number;
  showLegend?: boolean;
  yMin?: number;
  yMax?: number;
}) {
  const option = useMemo(() => {
    const legend = showLegend ?? series.length > 1;
    const out = series.map((s, i) => {
      const color = seriesColor(s.colorIndex ?? i);
      const data = s.points.map((p) => [p.t, p.v, p.period ?? null]);
      const common = {
        name: s.name, data, emphasis: { focus: "series" }, itemStyle: { color },
        markPoint: undefined as unknown,
        markLine: undefined as unknown,
      };
      if (i === 0 && markers?.length) {
        const byT = new Map(s.points.map((p) => [p.t, p.v]));
        common.markPoint = {
          symbol: "circle", symbolSize: 9, label: { show: false },
          itemStyle: { color: "#fab219", borderColor: INK.surface, borderWidth: 2 },
          data: markers.filter((m) => byT.get(m.t) != null).map((m) => ({ coord: [m.t, byT.get(m.t)], name: m.label })),
          tooltip: { formatter: (p: { name: string }) => `Outlier flag: ${p.name}` },
        };
      }
      if (i === 0 && (selected || baseline !== undefined)) {
        const lines: object[] = [];
        if (selected) lines.push({ xAxis: selected, lineStyle: { color: "#e8a33d", type: "solid", width: 1 },
          label: { show: false } });
        if (baseline !== undefined) lines.push({ yAxis: baseline, lineStyle: { color: INK.axis, type: "solid" },
          label: { show: false } });
        common.markLine = { symbol: "none", silent: true, data: lines };
      }
      if (s.kind === "bar") {
        return { ...common, type: "bar", stack: s.stack, barMaxWidth: 14,
          itemStyle: { color, borderRadius: [2, 2, 0, 0] } };
      }
      return {
        ...common, type: "line", showSymbol: false, symbolSize: 8, stack: s.stack,
        lineStyle: { width: s.dashed ? 1.5 : 2, color, type: s.dashed ? "dashed" : "solid" },
        areaStyle: s.kind === "area" ? { opacity: s.stack ? 0.85 : 0.12, color } : undefined,
        connectNulls: false,
      };
    });
    return {
      animation: false,
      grid: { ...gridBase, top: legend ? 26 : 12, bottom: zoom ? 44 : 20 },
      legend: legend ? { ...legendBase, data: series.map((s) => s.name) } : undefined,
      tooltip: {
        ...tooltipBase,
        trigger: "axis",
        axisPointer: { type: "line", lineStyle: { color: "#3fb6d3", width: 1 } },
        formatter: (ps: { seriesName: string; color: string; data: [string, number | null, string | null] }[]) => {
          if (!ps.length) return "";
          const head = ps[0].data[2] ?? String(ps[0].data[0]).slice(0, 10);
          const rows = ps.map((p) => `<div style="display:flex;gap:10px;justify-content:space-between">
            <span><span style="display:inline-block;width:8px;height:3px;background:${p.color};margin-right:6px;vertical-align:middle"></span>${p.seriesName}</span>
            <b style="font-variant-numeric:tabular-nums">${fmtValue(p.data[1], unit, decimals, false)}</b></div>`).join("");
          return `<div style="font-size:11px;min-width:160px"><div style="color:${INK.muted};margin-bottom:4px">${head}</div>${rows}
            ${onPointClick ? `<div style="color:${INK.muted};margin-top:4px;font-size:10px">Click to investigate</div>` : ""}</div>`;
        },
      },
      xAxis: axisTime(),
      yAxis: { ...axisValue(unit, decimals), ...(yMin !== undefined ? { min: yMin, scale: false } : {}),
        ...(yMax !== undefined ? { max: yMax } : {}) },
      dataZoom: zoom ? [{ type: "inside" }, { type: "slider", height: 16, bottom: 6, borderColor: INK.axis,
        textStyle: { color: INK.muted, fontSize: 9 }, fillerColor: "rgba(63,182,211,0.12)" }] : undefined,
      series: out,
    };
  }, [series, unit, decimals, zoom, markers, selected, baseline, showLegend, onPointClick, yMin, yMax]);

  return (
    <EChart
      option={option}
      height={height}
      group={group}
      ariaLabel={`Time series chart: ${series.map((s) => s.name).join(", ")} (${unit})`}
      onClick={onPointClick ? (p) => {
        const s = series[p.seriesIndex ?? -1];
        const d = p.data as [string, number | null, string | null] | undefined;
        if (s && d) onPointClick(s.key, { t: d[0], v: d[1], period: d[2] });
      } : undefined}
    />
  );
}
