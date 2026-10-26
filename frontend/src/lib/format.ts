// Number and date formatting. Units always travel with values; nothing is shown unit-less.

const nf = (d: number) => new Intl.NumberFormat("en-GB", { minimumFractionDigits: d, maximumFractionDigits: d });

export function fmtNumber(v: number | null | undefined, decimals = 1): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return "–";
  return nf(decimals).format(v);
}

export function fmtCompact(v: number | null | undefined): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return "–";
  const a = Math.abs(v);
  if (a >= 1e12) return `${fmtNumber(v / 1e12, 2)}tn`;
  if (a >= 1e9) return `${fmtNumber(v / 1e9, 1)}bn`;
  if (a >= 1e6) return `${fmtNumber(v / 1e6, 1)}m`;
  if (a >= 1e4) return `${fmtNumber(v / 1e3, 1)}k`;
  return fmtNumber(v, a < 10 ? 2 : 0);
}

/** Format a value with its unit. £m values are shown in £bn above £1,000m (exact value stays available). */
export function fmtValue(v: number | null | undefined, unit: string, decimals = 1, compact = true): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return "–";
  switch (unit) {
    case "%":
      return `${fmtNumber(v, decimals)}%`;
    case "% of GDP":
      return `${fmtNumber(v, decimals)}%`;
    case "% of generation":
      return `${fmtNumber(v, decimals)}%`;
    case "£m":
      return compact && Math.abs(v) >= 1000 ? `£${fmtNumber(v / 1000, 1)}bn` : `£${fmtNumber(v, 0)}m`;
    case "£m nominal":
      return compact && Math.abs(v) >= 1000 ? `£${fmtNumber(v / 1000, 1)}bn` : `£${fmtNumber(v, 0)}m`;
    case "£bn":
      return `£${fmtNumber(v, decimals)}bn`;
    case "£":
      return compact && Math.abs(v) >= 1e6 ? `£${fmtCompact(v)}` : `£${fmtNumber(v, decimals)}`;
    case "pence per litre":
      return `${fmtNumber(v, decimals)}p/l`;
    case "gCO2/kWh":
      return `${fmtNumber(v, 0)} gCO₂/kWh`;
    default:
      if (unit.startsWith("index")) return fmtNumber(v, decimals);
      if (compact && Math.abs(v) >= 1e5) return `${fmtCompact(v)}${unit ? " " + unit : ""}`;
      return `${fmtNumber(v, decimals)}${unit && !unit.includes(" per ") ? " " + unit : ""}`;
  }
}

export function fmtChange(v: number | null | undefined, unit: "pp" | "%" | string, decimals = 2): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return "–";
  const sign = v > 0 ? "+" : v < 0 ? "−" : "±";
  return `${sign}${fmtNumber(Math.abs(v), decimals)}${unit === "pp" ? "pp" : "%"}`;
}

export function fmtDateTime(s: string | null | undefined): string {
  if (!s) return "–";
  const d = new Date(s);
  if (Number.isNaN(d.getTime())) return s;
  return d.toLocaleString("en-GB", { year: "numeric", month: "short", day: "2-digit", hour: "2-digit",
    minute: "2-digit", timeZone: "Europe/London", timeZoneName: "short" });
}

export function fmtDate(s: string | null | undefined): string {
  if (!s) return "–";
  const d = new Date(s);
  if (Number.isNaN(d.getTime())) return s;
  return d.toLocaleDateString("en-GB", { year: "numeric", month: "short", day: "2-digit", timeZone: "Europe/London" });
}

export function ago(s: string | null | undefined): string {
  if (!s) return "never";
  const ms = Date.now() - new Date(s).getTime();
  const m = Math.round(ms / 60000);
  if (m < 60) return `${m} min ago`;
  const h = Math.round(m / 60);
  if (h < 48) return `${h} h ago`;
  return `${Math.round(h / 24)} d ago`;
}

export const FREQ_LABEL: Record<string, string> = {
  HH: "Half-hourly", D: "Daily", W: "Weekly", M: "Monthly", Q: "Quarterly", A: "Annual",
};

export const LATENCY_LABEL: Record<string, string> = {
  official_release: "Official release (scheduled)",
  daily_published: "Daily, published end of day (T+1)",
  near_real_time: "Near real-time (half-hourly)",
  snapshot: "Periodic snapshot",
  on_demand: "Queried on demand",
};

/** Chart timestamp for an observation: half-hourly series use the period key (date + time), others the start date. */
export function obsTime(o: { period: string; period_start: string }, frequency: string): string {
  return frequency === "HH" ? o.period.replace("Z", ":00Z") : o.period_start;
}

/** Signed number without a unit (e.g. score points). */
export function fmtSigned(v: number | null | undefined, decimals = 1): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return "–";
  return `${v > 0 ? "+" : v < 0 ? "−" : "±"}${fmtNumber(Math.abs(v), decimals)}`;
}
