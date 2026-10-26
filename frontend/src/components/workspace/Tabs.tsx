"use client";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useMemo, useState } from "react";
import { CheckCircle2, Lightbulb, MessageSquareQuote, XCircle } from "lucide-react";
import { api, qs, type Analysis, type SeriesDetail } from "@/lib/api";
import { INK, seriesColor } from "@/lib/colors";
import { fmtChange, fmtDateTime, fmtNumber, fmtValue, obsTime } from "@/lib/format";
import { useObservations } from "@/lib/hooks";
import { EChart } from "@/components/charts/EChart";
import { baseText, gridBase, tooltipBase } from "@/components/charts/theme";
import { TimeSeriesChart } from "@/components/charts/TimeSeriesChart";
import { DataTable } from "@/components/data/DataTable";
import { NativeSelect, Panel, Seg, Stat } from "@/components/data/Panel";

type P = { d: SeriesDetail; a?: Analysis };

export function ObservationsTab({ d, a, selected, onSelect, geo, dim, from, to }: P & {
  selected: string | null; onSelect: (p: string) => void; geo: string | null; dim: string | null; from: string | null; to: string | null;
}) {
  const obs = useObservations(d.identity.id, { geo, dim, start: from, end: to });
  const byPeriod = new Map((a?.points ?? []).map((p) => [p.period, p]));
  const rows = (obs.data?.observations ?? []).map((o) => ({ ...o, pop: byPeriod.get(o.period)?.pop ?? null, yoy: byPeriod.get(o.period)?.yoy ?? null }));
  const u = d.identity.unit;
  const cu = a?.change_unit ?? "%";
  return (
    <Panel title={`Raw observations (${rows.length})`} subtitle="Values exactly as retrieved; changes computed by this platform. Sort any column; click a row to select it."
      loading={obs.isLoading} actions={<span className="text-[10px] text-muted-foreground">source unit: {d.provenance.source_unit || u}</span>}>
      <DataTable
        rows={[...rows].reverse()}
        rowKey={(r) => r.period}
        selectedKey={selected}
        onRowClick={(r) => onSelect(r.period)}
        maxHeight={420}
        caption="Observations"
        columns={[
          { key: "period", header: "Period", value: (r) => r.period_start, render: (r) => r.period },
          { key: "value", header: `Value (${u})`, align: "right", value: (r) => r.value, render: (r) => fmtValue(r.value, u, d.identity.decimals, false) },
          { key: "pop", header: `Δ period (${cu})`, align: "right", value: (r) => r.pop, render: (r) => fmtChange(r.pop, cu) },
          { key: "yoy", header: `Δ year (${cu})`, align: "right", value: (r) => r.yoy, render: (r) => fmtChange(r.yoy, cu) },
          { key: "status", header: "Status", value: (r) => r.status },
          { key: "flags", header: "Source flags", value: (r) => JSON.stringify(r.flags ?? {}),
            render: (r) => <span className="text-[10px] text-muted-foreground">{Object.entries(r.flags ?? {}).filter(([k]) => k !== "lr_region").map(([k, v]) => `${k}: ${v}`).join(" · ")}</span> },
          { key: "release", header: "Published", value: (r) => r.release_date, render: (r) => <span className="text-muted-foreground">{fmtDateTime(r.release_date)}</span> },
          { key: "retrieved", header: "Retrieved", value: (r) => r.retrieved_at, render: (r) => <span className="text-muted-foreground">{fmtDateTime(r.retrieved_at)}</span> },
          { key: "run", header: "Run", value: (r) => r.run_id, render: (r) => r.run_id ? <Link className="text-cyan hover:underline" href={`/sources?run=${r.run_id}`}>#{r.run_id}</Link> : "–" },
        ]}
      />
    </Panel>
  );
}

export function StatisticsTab({ d, a, onSelect }: P & { onSelect: (p: string) => void }) {
  if (!a) return null;
  const u = d.identity.unit;
  const c = a.context;
  const v = a.volatility;
  const m = a.missing;
  return (
    <div className="grid grid-cols-1 gap-2 lg:grid-cols-2">
      <Panel title="Historical position" subtitle="Across all retrieved history (not only the selected range)">
        <div className="grid grid-cols-3 gap-3">
          <Stat label="Minimum" value={fmtValue(c.min, u, d.identity.decimals)} sub={c.min_at} />
          <Stat label="Maximum" value={fmtValue(c.max, u, d.identity.decimals)} sub={c.max_at} />
          <Stat label="10-year mean" value={fmtValue(c.mean_10y, u, d.identity.decimals)} />
          <Stat label="10-year percentile" value={c.percentile_10y != null ? `${fmtNumber(c.percentile_10y, 0)}th` : "–"} />
          <Stat label="First observation" value={c.first ?? "–"} />
          <Stat label="Observations" value={c.count ?? 0} />
        </div>
      </Panel>
      <Panel title="Volatility" subtitle={v.available ? `Std. dev. of period-on-period changes (${v.unit})` : v.reason}>
        {v.available && (
          <div className="grid grid-cols-3 gap-3">
            <Stat label="All history" value={fmtNumber(v.std_all, 3)} sub={`n = ${v.n}`} />
            <Stat label="Recent" value={fmtNumber(v.std_recent, 3)} sub={`last ${v.recent_n}`} />
            <Stat label="Mean |change|" value={fmtNumber(v.mean_abs_change, 3)} />
          </div>
        )}
      </Panel>
      <Panel title="Missing data & gaps" subtitle={m.note}>
        <div className="grid grid-cols-3 gap-3">
          <Stat label="Observations" value={m.observations} />
          <Stat label="Null values" value={m.null_values} sub={m.null_periods.slice(-4).join(", ") || undefined} />
          <Stat label="Sequence gaps" value={m.gaps_in_sequence} sub={m.gap_periods.slice(-4).join(", ") || undefined} />
        </div>
        {m.suppressed.length > 0 && <p className="mt-2 text-[10px] text-warning">Suppressed by source: {m.suppressed.join(", ")}</p>}
      </Panel>
      <Panel title="Uncertainty" subtitle="Only what the source publishes is shown; nothing is estimated here">
        <p className="text-[11px]">{a.uncertainty.text}</p>
        {a.uncertainty.values.length > 0 && (
          <table className="mt-2 w-full text-[11px]">
            <thead className="text-muted-foreground"><tr><th className="text-left">Period</th><th className="text-right">95% CI (pp)</th><th className="text-right">CV (%)</th><th className="text-left pl-2">Reliability</th></tr></thead>
            <tbody>{a.uncertainty.values.slice(-8).map((x, i) => (
              <tr key={i} className="border-t border-border/50"><td>{String(x.period)}</td><td className="text-right tabular">{x.ci95_pp != null ? `±${x.ci95_pp}` : "–"}</td>
                <td className="text-right tabular">{x.cv_pct != null ? String(x.cv_pct) : "–"}</td><td className="pl-2 text-muted-foreground">{String(x.reliability ?? "")}</td></tr>))}
            </tbody>
          </table>
        )}
      </Panel>
      <Panel title={`Outlier flags (${a.outliers.length})`} subtitle="Robust z-score (median/MAD) of period-on-period changes, |z| ≥ 3.5. A flag prompts investigation; it is not an error." className="lg:col-span-2">
        <DataTable rows={[...a.outliers].reverse()} rowKey={(o) => o.period} onRowClick={(o) => onSelect(o.period)} maxHeight={220}
          columns={[
            { key: "p", header: "Period", value: (o) => o.period_start, render: (o) => o.period },
            { key: "c", header: "Change", align: "right", value: (o) => o.change, render: (o) => fmtChange(o.change, o.change_unit) },
            { key: "z", header: "Robust z", align: "right", value: (o) => o.robust_z },
          ]} />
      </Panel>
      <Panel title="Seasonal decomposition" subtitle={a.decomposition.available ? `${a.decomposition.method} · seasonal strength ${fmtNumber(a.decomposition.seasonal_strength, 2)}` : a.decomposition.reason} className="lg:col-span-2">
        {a.decomposition.available && a.decomposition.points && (
          <div className="grid grid-cols-1 gap-2 md:grid-cols-3">
            {(["trend", "seasonal", "resid"] as const).map((k, i) => (
              <div key={k}>
                <div className="text-[10px] uppercase tracking-wider text-muted-foreground">{k === "resid" ? "Residual" : k}</div>
                <TimeSeriesChart height={140} unit={k === "trend" ? u : `${u} deviation`} showLegend={false}
                  series={[{ key: k, name: k, colorIndex: i, points: a.decomposition.points!.map((p) => ({ t: p.period_start, v: p[k] })) }]} />
              </div>
            ))}
            <p className="md:col-span-3 text-[10px] text-muted-foreground">{a.decomposition.caveat}</p>
          </div>
        )}
      </Panel>
    </div>
  );
}

export function ComparisonsTab({ d, a, geo, dim, onGeo, onSeries, onDim }: P & {
  geo: string | null; dim: string | null; onGeo: (g: string) => void; onSeries: (id: string) => void; onDim: (d: string) => void;
}) {
  if (!a) return null;
  const u = d.identity.unit;
  const regions = a.comparables.regions ?? [];
  const inds = a.comparables.industries ?? [];
  const barOption = (rows: { label: string; value: number; sel: boolean }[], unit: string) => ({
    animation: false, grid: { ...gridBase, top: 4, bottom: 4 },
    tooltip: { ...tooltipBase, formatter: (p: { dataIndex: number }) => `${rows[p.dataIndex].label}: <b>${fmtValue(rows[p.dataIndex].value, unit, d.identity.decimals, false)}</b>` },
    xAxis: { type: "value", axisLabel: { ...baseText, formatter: (v: number) => fmtValue(v, unit, 0) }, splitLine: { lineStyle: { color: INK.grid } } },
    yAxis: { type: "category", inverse: true, data: rows.map((r) => r.label), axisLabel: { ...baseText, color: INK.secondary }, axisTick: { show: false }, axisLine: { show: false } },
    series: [{ type: "bar", barMaxWidth: 12, data: rows.map((r) => ({ value: r.value, itemStyle: { color: r.sel ? "#e8a33d" : seriesColor(0), borderRadius: [0, 3, 3, 0] } })) }],
  });
  const rr = [...regions].sort((x, y) => y.value - x.value).map((r) => ({ label: r.name, value: r.value, sel: r.geo === geo, geo: r.geo }));
  return (
    <div className="grid grid-cols-1 gap-2 lg:grid-cols-2">
      {regions.length > 0 && (
        <Panel title="Comparable regions & nations" subtitle={`Latest period per area (${regions[0]?.period}); click to switch geography`}>
          <EChart height={Math.max(160, rr.length * 20)} option={barOption(rr, u)} onClick={(p) => rr[p.dataIndex ?? -1] && onGeo(rr[p.dataIndex!].geo)} />
          {geo && geo.startsWith("E12") && (
            <Link href={`/regions?geo=${geo}`} className="mt-1 inline-block text-[11px] text-cyan hover:underline">Drill down to local authorities in this region →</Link>
          )}
        </Panel>
      )}
      {inds.length > 0 && (
        <Panel title="Comparable industries (SIC 2007 sections)" subtitle={inds[0]?.yoy !== undefined ? "Output index y/y % change, latest month; click to switch" : "Latest values by section; click to switch"}>
          {(() => {
            const rows = [...inds].sort((x, y) => (y.yoy ?? y.value) - (x.yoy ?? x.value)).map((r) => ({
              label: r.title.replace("Output: ", ""), value: r.yoy ?? r.value, sel: r.series_id === d.identity.id || r.dim === dim, r }));
            return <EChart height={Math.max(200, rows.length * 18)} option={barOption(rows, inds[0]?.yoy !== undefined ? "%" : u)}
              onClick={(p) => { const x = rows[p.dataIndex ?? -1]?.r; if (!x) return; if (x.series_id) onSeries(x.series_id); else if (x.dim) onDim(x.dim); }} />;
          })()}
        </Panel>
      )}
      {!regions.length && !inds.length && (
        <Panel title="Comparisons" empty="This series is published only for the UK total by its source; no regional or industry breakdown is available (none is inferred)." />
      )}
      <Panel title="Related indicators" subtitle="Defined in the catalogue as relevant context" className="lg:col-span-2">
        <ul className="grid grid-cols-1 gap-1 md:grid-cols-2 xl:grid-cols-3">
          {d.related.map((r) => (
            <li key={r.id}>
              <button onClick={() => onSeries(r.id)} className="flex w-full items-center justify-between gap-2 rounded border px-2 py-1 text-left text-[11px] hover:bg-accent">
                <span className="truncate">{r.title}</span>
                <span className="tabular text-muted-foreground">{r.latest ? `${fmtValue(r.latest.value, r.unit, r.decimals)} · ${r.latest.period}` : "–"}</span>
              </button>
            </li>
          ))}
        </ul>
      </Panel>
    </div>
  );
}

interface CorrResp {
  frequency: string; basis: string; basis_description: string; aggregation: string; data_status: string;
  contemporaneous: { n: number; pearson: number | null; spearman: number | null; p_value: number | null; pearson_ci95?: number[] | null; start?: string; end?: string };
  lags: { lag: number; pearson: number | null; n: number }[]; best_lag: { lag: number; pearson: number | null; n: number } | null;
  lag_convention: string; warnings: string[];
}

export function RelationshipsTab({ d, a, geo, from }: P & { geo: string | null; from: string | null }) {
  const [other, setOther] = useState<string | null>(null);
  const [basis, setBasis] = useState<"changes" | "levels">("changes");
  const target = other ?? a?.relationships[0]?.series_id ?? d.identity.related[0] ?? null;
  const q = useQuery({
    queryKey: ["corr", d.identity.id, target, basis, geo, from],
    queryFn: () => api<CorrResp>(`/correlate${qs({ a: d.identity.id, b: target, basis, geo_a: geo, start: from, max_lag: 12 })}`),
    enabled: !!target,
  });
  const c = q.data;
  const option = useMemo(() => c ? {
    animation: false, grid: { ...gridBase, top: 10 },
    tooltip: { ...tooltipBase, trigger: "axis", formatter: (ps: { dataIndex: number }[]) => { const l = c.lags[ps[0].dataIndex]; return `lag ${l.lag}: r = ${fmtNumber(l.pearson, 3)} (n = ${l.n})`; } },
    xAxis: { type: "category", data: c.lags.map((l) => String(l.lag)), name: "lag (periods)", nameLocation: "middle", nameGap: 22, nameTextStyle: baseText, axisLabel: baseText },
    yAxis: { type: "value", min: -1, max: 1, axisLabel: baseText, splitLine: { lineStyle: { color: INK.grid } } },
    series: [{ type: "bar", barMaxWidth: 10, data: c.lags.map((l) => ({ value: l.pearson, itemStyle: { color: l.lag === c.best_lag?.lag ? "#e8a33d" : seriesColor(0), borderRadius: 2 } })) }],
  } : {}, [c]);
  return (
    <div className="grid grid-cols-1 gap-2 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.3fr)]">
      <Panel title="Co-movement with related indicators" subtitle={a?.relationship_note}>
        <DataTable rows={a?.relationships ?? []} rowKey={(r) => r.series_id} selectedKey={target} onRowClick={(r) => setOther(r.series_id)} maxHeight={300}
          columns={[
            { key: "t", header: "Indicator", value: (r) => r.title },
            { key: "r", header: "r (changes)", align: "right", value: (r) => r.pearson, render: (r) => fmtNumber(r.pearson, 2) },
            { key: "n", header: "n", align: "right", value: (r) => r.n },
            { key: "lag", header: "Peak lag", align: "right", value: (r) => r.best_lag?.lag ?? null, render: (r) => r.best_lag ? `${r.best_lag.lag} (r ${fmtNumber(r.best_lag.pearson, 2)})` : "–" },
          ]} />
        <p className="mt-2 text-[10px] text-muted-foreground">Computed on period-on-period changes at the coarser common frequency (series averaged within periods). Only real (non-demo) data is used.</p>
      </Panel>
      <Panel title={`Lag analysis${target ? ` vs ${d.related.find((r) => r.id === target)?.title ?? target}` : ""}`} subtitle={c?.basis_description}
        loading={q.isLoading} error={(q.error as Error | null)?.message}
        actions={<Seg value={basis} onChange={setBasis} label="Basis" options={[{ value: "changes", label: "Changes" }, { value: "levels", label: "Levels" }]} />}>
        {c && (
          <>
            <div className="mb-1 grid grid-cols-4 gap-3">
              <Stat label="Pearson r" value={fmtNumber(c.contemporaneous.pearson, 3)} sub={c.contemporaneous.pearson_ci95 ? `95% CI ${fmtNumber(c.contemporaneous.pearson_ci95[0], 2)} to ${fmtNumber(c.contemporaneous.pearson_ci95[1], 2)}` : undefined} />
              <Stat label="Spearman ρ" value={fmtNumber(c.contemporaneous.spearman, 3)} />
              <Stat label="n / window" value={c.contemporaneous.n} sub={`${c.contemporaneous.start ?? ""} – ${c.contemporaneous.end ?? ""}`} />
              <Stat label="Peak |r| lag" value={c.best_lag ? c.best_lag.lag : "–"} sub={c.best_lag ? `r ${fmtNumber(c.best_lag.pearson, 3)}` : undefined} />
            </div>
            <EChart option={option} height={190} ariaLabel="Cross-correlation by lag" />
            <p className="text-[10px] text-muted-foreground">{c.lag_convention} {c.aggregation}</p>
            <ul className="mt-1 list-disc space-y-0.5 pl-4 text-[10px] text-warning">{c.warnings.map((w) => <li key={w}>{w}</li>)}</ul>
          </>
        )}
      </Panel>
    </div>
  );
}

interface RevResp {
  detected: { period: string; geo: string; dim: string; old_value: number | null; new_value: number | null; revision: number | null; detected_at: string; run_id: number | null }[];
  published_versions: { label: string; updateDate: string; correctionNotice: string | null; uri: string }[];
  version_count: number | null; supports_vintages: boolean; note: string;
}
interface VintResp {
  periods: string[]; current: Record<string, number | null>;
  vintages: { label: string; updateDate: string; correctionNotice: string | null; url: string; values: Record<string, number | null> }[];
  errors: { label: string; message: string }[]; note: string;
}

export function RevisionsTab({ d, geo, dim }: { d: SeriesDetail; geo: string | null; dim: string | null }) {
  const [load, setLoad] = useState(false);
  const rev = useQuery({ queryKey: ["rev", d.identity.id, geo, dim], queryFn: () => api<RevResp>(`/series/${d.identity.id}/revisions${qs({ geo, dim })}`) });
  const vin = useQuery({ queryKey: ["vint", d.identity.id], queryFn: () => api<VintResp>(`/series/${d.identity.id}/vintages?n=5&periods=12`), enabled: load });
  const u = d.identity.unit;
  return (
    <div className="grid grid-cols-1 gap-2">
      <Panel title="Revisions detected by this platform" subtitle={rev.data?.note} loading={rev.isLoading}
        empty={rev.data && !rev.data.detected.length ? "No value has changed between this platform's retrievals yet." : null}>
        <DataTable rows={rev.data?.detected ?? []} rowKey={(r) => `${r.period}-${r.detected_at}-${r.geo}-${r.dim}`} maxHeight={240}
          columns={[
            { key: "p", header: "Period", value: (r) => r.period },
            { key: "o", header: "Previous", align: "right", value: (r) => r.old_value, render: (r) => fmtValue(r.old_value, u, d.identity.decimals, false) },
            { key: "n", header: "Revised", align: "right", value: (r) => r.new_value, render: (r) => fmtValue(r.new_value, u, d.identity.decimals, false) },
            { key: "r", header: "Revision", align: "right", value: (r) => r.revision, render: (r) => fmtNumber(r.revision, 3) },
            { key: "at", header: "Detected", value: (r) => r.detected_at, render: (r) => fmtDateTime(r.detected_at) },
            { key: "run", header: "Run", value: (r) => r.run_id },
          ]} />
      </Panel>
      {rev.data?.supports_vintages && (
        <Panel title={`Published vintages (ONS version history: ${rev.data.version_count ?? 0} versions)`}
          subtitle="Compare the latest values with earlier published versions of the same series"
          actions={!load ? <button onClick={() => setLoad(true)} className="rounded border border-primary/50 px-2 py-0.5 text-[11px] text-primary hover:bg-primary/10">Load last 5 vintages</button> : null}
          loading={vin.isLoading} error={(vin.error as Error | null)?.message}>
          {vin.data ? (
            <div className="overflow-auto">
              <table className="w-full text-[11px]">
                <thead className="text-muted-foreground"><tr><th className="text-left">Period</th>
                  {vin.data.vintages.map((v) => <th key={v.label} className="text-right"><a href={v.url} target="_blank" rel="noreferrer" className="hover:text-cyan">{v.label}</a><div className="text-[9px]">{v.updateDate.slice(0, 10)}</div></th>)}
                  <th className="text-right text-foreground">Current</th></tr></thead>
                <tbody>{[...vin.data.periods].reverse().map((p) => (
                  <tr key={p} className="border-t border-border/50"><td>{p}</td>
                    {vin.data!.vintages.map((v) => { const x = v.values[p]; const cur = vin.data!.current[p];
                      return <td key={v.label} className={`text-right tabular ${x != null && cur != null && Math.abs(x - cur) > 1e-9 ? "text-warning" : ""}`}>{x == null ? "·" : fmtNumber(x, d.identity.decimals)}</td>; })}
                    <td className="text-right tabular font-medium">{fmtNumber(vin.data!.current[p], d.identity.decimals)}</td></tr>))}
                </tbody>
              </table>
              <p className="mt-1 text-[10px] text-muted-foreground">Amber = differs from the current published value. “·” = period not yet published in that vintage. {vin.data.note}</p>
            </div>
          ) : <p className="text-[11px] text-muted-foreground">Vintages are fetched on demand from ONS (cached; immutable).</p>}
        </Panel>
      )}
      {!rev.data?.supports_vintages && (
        <Panel title="Publisher revision history" empty="This source does not expose earlier published versions through its API; only revisions detected between this platform's retrievals are shown." />
      )}
    </div>
  );
}

interface ScenResp { available: boolean; reason?: string; formula?: string; label?: string; step?: number; step_unit?: string;
  start?: { period_start: string; value: number }; points?: { period_start: string; value: number }[]; data_status: string }

export function ScenarioTab({ d, a, geo, dim }: P & { geo: string | null; dim: string | null }) {
  const [mode, setMode] = useState<"trend" | "flat" | "custom">("trend");
  const [periods, setPeriods] = useState(12);
  const [value, setValue] = useState(0);
  const q = useQuery({
    queryKey: ["scen", d.identity.id, mode, periods, value, geo, dim],
    queryFn: () => api<ScenResp>(`/series/${d.identity.id}/scenario${qs({ mode, periods, value: mode === "custom" ? value : undefined, geo, dim })}`),
  });
  const hist = (a?.points ?? []).filter((p) => p.value != null).slice(-36);
  const s = q.data;
  const unitLabel = a?.change_unit === "pp" ? "pp per period" : "% per period";
  return (
    <Panel title="Transparent scenario (what-if)" subtitle={s?.label ?? "Mechanical projection from stated assumptions. Not a forecast."}
      loading={q.isLoading} error={(q.error as Error | null)?.message}
      actions={<>
        <Seg value={mode} onChange={setMode} label="Assumption" options={[{ value: "trend", label: "Recent average change" }, { value: "flat", label: "Unchanged" }, { value: "custom", label: "Custom" }]} />
        {mode === "custom" && <label className="text-[11px] text-muted-foreground">step <input type="number" step="0.1" value={value} onChange={(e) => setValue(Number(e.target.value))}
          className="h-7 w-16 rounded border bg-secondary px-1 text-foreground" /> {unitLabel}</label>}
        <NativeSelect label="Horizon" value={String(periods)} onChange={(v) => setPeriods(Number(v))} options={[6, 12, 24, 36].map((n) => ({ value: String(n), label: `${n} periods` }))} />
      </>}>
      {s && !s.available && <p className="text-[11px] text-muted-foreground">{s.reason}</p>}
      {s?.available && (
        <>
          <TimeSeriesChart height={240} unit={d.identity.unit} decimals={d.identity.decimals}
            series={[
              { key: "h", name: "Observed", points: hist.map((p) => ({ t: obsTime({ period: p.period ?? "", period_start: p.period_start }, d.identity.frequency), v: p.value, period: p.period })) },
              { key: "s", name: "Scenario (assumption-driven)", dashed: true, colorIndex: 3, points: [s.start!, ...s.points!].map((p) => ({ t: p.period_start, v: p.value })) },
            ]} />
          <div className="mt-1 rounded border bg-secondary/50 px-2 py-1 text-[11px]"><b>Formula:</b> <code>{s.formula}</code> · step {fmtNumber(s.step, 3)} {s.step_unit}</div>
        </>
      )}
    </Panel>
  );
}

const F_ICON = { fact: CheckCircle2, interpretation: MessageSquareQuote, hypothesis: Lightbulb };
const F_LABEL = { fact: "Facts (directly from displayed values)", interpretation: "Interpretations (contextual comparisons)", hypothesis: "Hypotheses (associations - unproven)" };

export function FindingsTab({ a }: { a?: Analysis }) {
  if (!a) return null;
  return (
    <div className="grid grid-cols-1 gap-2 lg:grid-cols-3">
      {(["fact", "interpretation", "hypothesis"] as const).map((t) => {
        const Icon = F_ICON[t];
        const items = a.findings.filter((f) => f.type === t);
        return (
          <Panel key={t} title={F_LABEL[t]} empty={items.length ? null : "None"}>
            <ul className="space-y-1.5">
              {items.map((f, i) => (
                <li key={i} className="flex gap-2 text-[11px] leading-relaxed">
                  <Icon className="mt-0.5 size-3.5 shrink-0" style={{ color: t === "fact" ? "#0ca30c" : t === "interpretation" ? "#3fb6d3" : "#fab219" }} aria-hidden />
                  <span>{f.text}</span>
                </li>
              ))}
            </ul>
          </Panel>
        );
      })}
      <p className="lg:col-span-3 text-[10px] text-muted-foreground">Findings are generated deterministically from the values shown (no AI model). Associations are never presented as causes.</p>
    </div>
  );
}

export function MethodologyTab({ d, a }: P) {
  const rules = Object.entries(d.rules);
  const NAMES: Record<string, string> = { pct_change: "% change", abs_change: "Absolute change", period_on_period: "Period-on-period", year_on_year: "Year-on-year",
    index: "Indexing (rebasing)", rolling_mean: "Rolling mean", decomposition: "Seasonal decomposition" };
  return (
    <div className="grid grid-cols-1 gap-2 lg:grid-cols-2">
      <Panel title="Statistically appropriate transformations" subtitle="Enforced by the API, based on measure type, frequency and adjustment">
        <ul className="space-y-1">
          {rules.map(([k, r]) => (
            <li key={k} className="flex gap-2 text-[11px]">
              {r.allowed ? <CheckCircle2 className="mt-0.5 size-3.5 shrink-0 text-good" aria-label="allowed" /> : <XCircle className="mt-0.5 size-3.5 shrink-0 text-critical" aria-label="refused" />}
              <div><b>{NAMES[k] ?? k}</b>{r.reason && <span className="text-muted-foreground"> — {r.reason}</span>}{r.caveat && <div className="text-[10px] text-warning">{r.caveat}</div>}</div>
            </li>
          ))}
        </ul>
      </Panel>
      <Panel title="Notes, comparability & limitations">
        <ul className="list-disc space-y-1 pl-4 text-[11px]">
          {d.identity.notes.map((n) => <li key={n}>{n}</li>)}
          {d.provenance.caveats.map((n) => <li key={n} className="text-muted-foreground">{n}</li>)}
          {d.provenance.key_note && <li>Source note: {d.provenance.key_note}</li>}
          <li>Uncertainty: {d.identity.uncertainty}</li>
          {a && Object.entries(a.method).map(([k, v]) => <li key={k} className="text-muted-foreground">{k}: {v}</li>)}
        </ul>
        {d.provenance.bulletins.length > 0 && (
          <div className="mt-2 text-[11px]">Methodology & commentary: {d.provenance.bulletins.map((b) => <a key={b} href={b} target="_blank" rel="noreferrer" className="mr-2 text-cyan hover:underline">latest bulletin ↗</a>)}</div>
        )}
        <div className="mt-1 text-[11px]">Source documentation: <a href={d.provenance.docs_url} target="_blank" rel="noreferrer" className="text-cyan hover:underline">{d.provenance.docs_url}</a></div>
      </Panel>
    </div>
  );
}
