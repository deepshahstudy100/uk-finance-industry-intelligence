// Typed client for the FastAPI backend. Requests go to same-origin /api/* (proxied by next.config rewrites).

export type DataStatus = "real" | "demo";
export type SeriesStatus =
  | "current" | "delayed" | "stale" | "unavailable" | "provisional" | "demo" | "disabled";

export interface Latest {
  period: string;
  value: number | null;
  status: string;
  release_date: string | null;
  retrieved_at: string | null;
}

export interface SeriesSummary {
  id: string;
  title: string;
  category: string;
  unit: string;
  frequency: string;
  measure_type: string;
  source_id: string;
  geography: string;
  dim_kind: string | null;
  industry: string | null;
  group: string | null;
  status: SeriesStatus;
  status_reasons: string[];
  decimals: number;
  enabled: boolean;
  data_status: DataStatus | null;
  latest?: Latest;
  change?: { vs_period: string; unit: "pp" | "%"; value: number | null };
  spark?: (number | null)[];
}

export interface Rule { allowed: boolean; reason: string; caveat: string }

export interface Provenance {
  source_id: string;
  source_name: string;
  publisher: string;
  dataset_identifier: string;
  source_title: string | null;
  request_url: string | null;
  source_page_url: string | null;
  dataset_url: string | null;
  bulletins: string[];
  docs_url: string;
  licence: string;
  licence_url: string;
  attribution: string;
  release_date: string | null;
  next_release: string | null;
  last_retrieved_at: string | null;
  last_run_id: number | null;
  latency_class: string;
  update_frequency: string;
  derived_from: string[];
  formula: string | null;
  modification_notice: string | null;
  source_unit: string | null;
  key_note: string | null;
  caveats: string[];
}

export interface SeriesIdentity {
  id: string; source_id: string; source_key: string; title: string; category: string; definition: string;
  unit: string; measure_type: string; frequency: string; seasonal_adjustment: string; geography: string;
  dim_kind: string | null; industry: string | null; industry_name: string | null;
  industry_classification: string | null; group: string | null; price_basis: string | null;
  base_period: string | null; decimals: number; notes: string[]; uncertainty: string; related: string[];
  derived_from: string[]; formula: string | null; enabled: boolean;
}

export interface SeriesDetail {
  identity: SeriesIdentity;
  provenance: Provenance;
  status: { status: SeriesStatus; reasons: string[] };
  data_status: DataStatus;
  rules: Record<string, Rule>;
  geographies: { code: string; name: string }[];
  dims: { code: string; label: string }[];
  default_geo: string;
  default_dim: string;
  revision_count: number;
  related: SeriesSummary[];
  versions: { label: string; updateDate: string; correctionNotice: string | null; uri: string }[];
  version_count: number | null;
}

export interface Observation {
  period: string; period_start: string; period_end: string; value: number | null; status: string;
  flags: Record<string, unknown>; geo: string; dim: string; release_date: string | null;
  retrieved_at: string; run_id: number | null; is_demo: boolean;
}

export interface ObservationsResponse {
  series_id: string; title: string; decimals: number; geo: string; dim: string; geo_name: string; dim_label: string; unit: string;
  frequency: string; data_status: DataStatus; observations: Observation[]; provenance: Provenance;
}

export interface AnalysisPoint {
  period: string | null; period_start: string; value: number | null; pop: number | null; yoy: number | null;
  rolling: number | null; indexed: number | null; status: string | null; flags: Record<string, unknown> | null;
}

export interface Finding { type: "fact" | "interpretation" | "hypothesis"; text: string; evidence: unknown[] }

export interface Outlier {
  period: string; period_start: string; change: number; change_unit: string; robust_z: number; method: string;
}

export interface Relationship {
  series_id: string; title: string; pearson: number | null; n: number; p_value: number | null;
  best_lag: { lag: number; pearson: number | null; n: number } | null; frequency: string; basis: string;
}

export interface Analysis {
  series_id: string; data_status: DataStatus; unit: string; change_unit: "pp" | "%"; window: number;
  rules: Record<string, Rule>; method: Record<string, string>; points: AnalysisPoint[];
  context: {
    min?: number; min_at?: string; max?: number; max_at?: string; mean_10y?: number | null;
    percentile_10y?: number | null; last_higher?: string | null; last_lower?: string | null; first?: string;
    count?: number;
  };
  volatility: { available: boolean; reason?: string; unit?: string; std_all?: number; std_recent?: number;
    recent_n?: number; mean_abs_change?: number; n?: number };
  missing: { observations: number; null_values: number; null_periods: string[]; gaps_in_sequence: number;
    gap_periods: string[]; suppressed: string[]; note: string };
  outliers: Outlier[];
  decomposition: { available: boolean; reason?: string; method?: string; seasonal_strength?: number;
    points?: { period_start: string; trend: number; seasonal: number; resid: number }[]; caveat?: string };
  relationships: Relationship[];
  relationship_note: string;
  uncertainty: { text: string; values: Record<string, unknown>[] };
  comparables: {
    regions?: { geo: string; name: string; period: string; value: number; flags: Record<string, unknown> }[];
    industries?: { series_id?: string; dim?: string; industry: string; title: string; period: string; value: number;
      yoy?: number }[];
  };
  findings: Finding[];
  notes: string[];
  geo_name: string;
  dim_label: string;
}

export interface SliceRow {
  geo: string; geo_name: string; dim: string; dim_label: string; value: number | null; status: string;
  flags: Record<string, unknown>; change: number | null; share: number | null;
}
export interface Slice {
  series_id: string; by: string; period: string | null; previous_period: string | null; periods: string[];
  rows: SliceRow[]; change_unit: string; unit: string; data_status: DataStatus; share_note: string | null;
}

export interface AlertItem {
  id: number; kind: string; severity: "info" | "warning" | "critical"; series_id: string | null;
  source_id: string | null; geo: string | null; dim: string | null; period: string | null; title: string;
  detail: string; created_at: string; updated_at: string; active: boolean;
}

export interface SourceRow {
  id: string; name: string; publisher: string; homepage: string; docs_url: string; api_base: string;
  licence: string; licence_url: string; attribution: string; auth: string;
  rate_limit: { requests: number; per_seconds: number; documented: boolean; note: string };
  update_frequency: string; latency_class: string; refresh_minutes: number; stale_after_hours: number;
  verification: string; caveats: string[]; status: string; status_reasons: string[];
  last_success_at: string | null; last_attempt_at: string | null; last_error: string | null;
  consecutive_failures: number; observations: number; series: string[];
  last_run: RunInfo | null;
}

export interface RunInfo {
  id: number; source_id: string; job: string; started_at: string; finished_at: string | null; status: string;
  fetched: number; inserted: number; updated: number; revised: number; unchanged: number; message: string | null;
  errors: { series_id: string | null; kind: string; message: string; url?: string }[]; request_count: number;
  requests?: { url: string; status: number | null; attempt: number; ms: number; bytes: number; via: string; at: string }[];
}

export interface Overview {
  kpis: SeriesSummary[];
  markets: SeriesSummary[];
  timeline_series: string[];
  alerts: AlertItem[];
  sources: { id: string; name: string; publisher: string; status: string; last_success_at: string | null;
    latency_class: string }[];
}

export interface Meta {
  demo_mode: "off" | "fallback" | "only"; companies_house_enabled: boolean; boe_fx_enabled: boolean;
  not_integrated: { name: string; reason: string }[]; series_count: number; source_count: number;
  paid_dependencies: string[]; statement: string;
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

export function qs(params: Record<string, string | number | boolean | null | undefined>): string {
  const u = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== "") u.set(k, String(v));
  }
  const s = u.toString();
  return s ? `?${s}` : "";
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path.startsWith("/api") ? path : `/api${path}`, {
    ...init,
    headers: { Accept: "application/json", ...(init?.headers || {}) },
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const j = await res.json();
      detail = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail ?? j);
    } catch {
      /* non-JSON error */
    }
    throw new ApiError(res.status, detail);
  }
  return res.json() as Promise<T>;
}

export function exportUrl(p: {
  series_id: string; geo?: string | null; dim?: string | null; start?: string | null; end?: string | null;
  format: "csv" | "json"; include_analysis?: boolean;
}): string {
  return `/api/export${qs(p)}`;
}
