import { INK, seriesColor } from "@/lib/colors";
import { fmtValue } from "@/lib/format";

export const baseText = { color: INK.muted, fontSize: 10, fontFamily: "var(--font-sans), system-ui, sans-serif" };

export function axisTime() {
  return {
    type: "time" as const,
    axisLine: { lineStyle: { color: INK.axis } },
    axisTick: { show: false },
    axisLabel: { ...baseText, hideOverlap: true },
    splitLine: { show: false },
  };
}

export function axisValue(unit: string, decimals = 1) {
  return {
    type: "value" as const,
    scale: true,
    axisLine: { show: false },
    axisLabel: { ...baseText, formatter: (v: number) => fmtValue(v, unit, Math.min(decimals, 1)) },
    splitLine: { lineStyle: { color: INK.grid } },
  };
}

export const tooltipBase = {
  backgroundColor: "#141b25",
  borderColor: "rgba(148,163,184,0.25)",
  textStyle: { color: INK.primary, fontSize: 11 },
  extraCssText: "box-shadow: 0 6px 24px rgba(0,0,0,0.45); border-radius: 6px;",
};

export const gridBase = { left: 8, right: 12, top: 18, bottom: 22, containLabel: true };

export function lineSeries(name: string, i: number, data: [string, number | null][], extra: object = {}) {
  return {
    name, type: "line" as const, data, showSymbol: false, symbolSize: 8, connectNulls: false,
    lineStyle: { width: 2, color: seriesColor(i) }, itemStyle: { color: seriesColor(i) },
    emphasis: { focus: "series" as const }, ...extra,
  };
}

export const legendBase = { top: 0, right: 0, textStyle: { ...baseText, color: INK.secondary }, itemWidth: 12,
  itemHeight: 3, icon: "rect" };
