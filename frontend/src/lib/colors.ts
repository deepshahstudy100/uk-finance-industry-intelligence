// Chart colour roles. Categorical slots are the dataviz reference dark palette, validated on our panel
// surface #121821 (all six checks pass; worst adjacent CVD ΔE 8.4). Assign in fixed order - never cycle.
export const SERIES = ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9", "#e66767"];

export const INK = {
  primary: "#e3e8ef",
  secondary: "#b9c3d0",
  muted: "#8a96a8",
  grid: "#1f2731",
  axis: "#2c3642",
  surface: "#121821",
};

// Sequential (magnitude) single-hue blue ramp, light -> dark is inverted on dark surfaces: low = darker.
export const SEQ_BLUE = ["#104281", "#1c5cab", "#2a78d6", "#5598e7", "#86b6ef", "#b7d3f6"];

// Diverging: red (negative) <- neutral grey -> blue (positive).
export const DIVERGING = { neg: "#e66767", mid: "#383835", pos: "#3987e5" };

export const STATUS_COLOR: Record<string, string> = {
  current: "#0ca30c",
  on_demand: "#8a96a8",
  provisional: "#3fb6d3",
  delayed: "#fab219",
  degraded: "#fab219",
  stale: "#ec835a",
  unavailable: "#d03b3b",
  not_configured: "#8a96a8",
  disabled: "#8a96a8",
  demo: "#c77dff",
};

export function seriesColor(i: number): string {
  return SERIES[Math.min(i, SERIES.length - 1)];
}
