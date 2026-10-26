"use client";
// Universal data-point explorer. Every chart, tile, map area, heatmap cell and table row in the app links here
// with ?series=&geo=&dim=&period= (+ the originating filters and a return path), so the user can move from a
// chart to the table, to the source record and back without losing context.
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useMemo, useState } from "react";
import { ArrowLeft, Download, ExternalLink, FileJson, Table2 } from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { exportUrl } from "@/lib/api";
import { fmtChange, fmtValue, FREQ_LABEL, obsTime } from "@/lib/format";
import { useAnalysis, useSeriesDetail, useSeriesList } from "@/lib/hooks";
import { TimeSeriesChart, type TSSeries } from "@/components/charts/TimeSeriesChart";
import { NativeSelect, Panel, Seg } from "@/components/data/Panel";
import { DemoBadge, StatusBadge } from "@/components/data/Status";
import { IdentityCard, ProvenanceCard, SelectedObservation } from "./Cards";
import {
  ComparisonsTab, FindingsTab, MethodologyTab, ObservationsTab, RelationshipsTab, RevisionsTab, ScenarioTab, StatisticsTab,
} from "./Tabs";

type View = "level" | "pop" | "yoy" | "indexed";

export function Workspace() {
  const sp = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const seriesId = sp.get("series");
  const from = sp.get("from");
  const to = sp.get("to");
  const ret = sp.get("return");
  const tab = sp.get("tab") ?? "observations";
  const [view, setView] = useState<View>("level");

  const setParam = useCallback((patch: Record<string, string | null>) => {
    const next = new URLSearchParams(sp.toString());
    for (const [k, v] of Object.entries(patch)) (v ? next.set(k, v) : next.delete(k));
    router.replace(`${pathname}?${next.toString()}`, { scroll: false });
  }, [sp, router, pathname]);

  const detail = useSeriesDetail(seriesId);
  const d = detail.data;
  const geo = sp.get("geo") ?? (d && sp.get("fgeo") && d.geographies.some((g) => g.code === sp.get("fgeo")) ? sp.get("fgeo") : null)
    ?? d?.default_geo ?? null;
  const dim = sp.get("dim") ?? d?.default_dim ?? null;
  const analysis = useAnalysis(seriesId && d ? seriesId : null, { geo, dim: dim ?? undefined, start: from, end: to });
  const a = analysis.data;

  const selPeriod = sp.get("period") ?? a?.points.filter((p) => p.value != null).at(-1)?.period ?? null;
  const selPoint = a?.points.find((p) => p.period === selPeriod) ?? null;

  const chartSeries: TSSeries[] = useMemo(() => {
    if (!a || !d) return [];
    const f = d.identity.frequency;
    const t = (p: { period: string | null; period_start: string }) =>
      obsTime({ period: p.period ?? "", period_start: p.period_start }, f);
    if (view === "level") {
      return [
        { key: "value", name: d.identity.title, points: a.points.map((p) => ({ t: t(p), v: p.value, period: p.period })) },
        { key: "rolling", name: `Rolling mean (${a.window})`, dashed: true, colorIndex: 6,
          points: a.points.map((p) => ({ t: t(p), v: p.rolling, period: p.period })) },
      ];
    }
    const key = view === "indexed" ? "indexed" : view;
    const label = view === "pop" ? `Period-on-period (${a.change_unit})` : view === "yoy" ? `Year-on-year (${a.change_unit})` : "Indexed (start = 100)";
    return [{ key: "value", name: label, kind: view === "indexed" ? "line" : "bar",
      points: a.points.map((p) => ({ t: t(p), v: p[key as "pop" | "yoy" | "indexed"], period: p.period })) }];
  }, [a, d, view]);

  if (!seriesId) return <SeriesPicker />;
  if (detail.error) return <p className="p-4 text-xs text-critical">{(detail.error as Error).message}</p>;
  if (!d) return <p className="p-4 text-xs text-muted-foreground">Loading definition…</p>;

  const idn = d.identity;
  const r = d.rules;
  const unitForView = view === "level" ? idn.unit : view === "indexed" ? "index" : a?.change_unit === "pp" ? "pp" : "%";
  const chartUnit = unitForView === "pp" ? "pp" : unitForView;
  const demo = (a?.data_status ?? d.data_status) === "demo";
  const geoName = d.geographies.find((g) => g.code === geo)?.name ?? a?.geo_name ?? geo;
  const dimLabel = d.dims.find((x) => x.code === dim)?.label;
  const markers = view === "level" ? (a?.outliers ?? []).map((o) => ({ t: o.period_start, label: `${o.period}: ${fmtChange(o.change, o.change_unit)} (z ${o.robust_z})` })) : [];
  const selT = selPoint ? obsTime({ period: selPoint.period ?? "", period_start: selPoint.period_start }, idn.frequency) : null;

  return (
    <div className="pb-6">
      {/* Header */}
      <div className="flex flex-wrap items-center gap-2 border-b px-3 py-2">
        {ret ? (
          <Link href={ret} className="inline-flex items-center gap-1 rounded border px-2 py-1 text-[11px] text-muted-foreground hover:text-foreground">
            <ArrowLeft className="size-3.5" /> Back
          </Link>
        ) : null}
        <nav aria-label="Breadcrumb" className="flex min-w-0 flex-wrap items-center gap-1 text-[11px] text-muted-foreground">
          <span className="capitalize">{idn.category.replace("_", " ")}</span><span>›</span>
          <span className="font-semibold text-foreground">{idn.title}</span>
          {geoName && <><span>›</span><span>{geoName}</span></>}
          {dimLabel && dim !== "_" && <><span>›</span><span>{dimLabel}</span></>}
          {selPeriod && <><span>›</span><span className="text-primary tabular">{selPeriod}</span></>}
        </nav>
        <StatusBadge status={d.status.status} reasons={d.status.reasons} />
        {demo && <DemoBadge />}
        <div className="ml-auto flex flex-wrap items-center gap-1.5">
          <a href={exportUrl({ series_id: idn.id, geo, dim, start: from, end: to, format: "csv" })} className="inline-flex items-center gap-1 rounded border px-2 py-1 text-[11px] hover:bg-accent">
            <Download className="size-3.5" /> CSV</a>
          <a href={exportUrl({ series_id: idn.id, geo, dim, start: from, end: to, format: "csv", include_analysis: true })} className="inline-flex items-center gap-1 rounded border px-2 py-1 text-[11px] hover:bg-accent">
            <Table2 className="size-3.5" /> CSV + analysis</a>
          <a href={exportUrl({ series_id: idn.id, geo, dim, start: from, end: to, format: "json", include_analysis: true })} className="inline-flex items-center gap-1 rounded border px-2 py-1 text-[11px] hover:bg-accent">
            <FileJson className="size-3.5" /> JSON</a>
          {d.provenance.source_page_url && (
            <a href={d.provenance.source_page_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 rounded border border-primary/40 px-2 py-1 text-[11px] text-primary hover:bg-primary/10">
              <ExternalLink className="size-3.5" /> Source</a>
          )}
        </div>
      </div>

      {/* Controls */}
      <div className="flex flex-wrap items-center gap-3 px-3 py-2">
        <SeriesSwitch current={idn.id} onChange={(id) => setParam({ series: id, geo: null, dim: null, period: null })} />
        {d.geographies.length > 1 && (
          <NativeSelect label="Geography" value={geo ?? ""} onChange={(v) => setParam({ geo: v, period: null })}
            options={sortGeos(d.geographies).map((g) => ({ value: g.code, label: g.name }))} />
        )}
        {d.dims.length > 1 && (
          <NativeSelect label={idn.dim_kind === "sic_section" ? "Industry (SIC 2007)" : "Breakdown"} value={dim ?? ""}
            onChange={(v) => setParam({ dim: v, period: null })} options={d.dims.map((x) => ({ value: x.code, label: x.label }))} />
        )}
        <Seg<View> value={view} onChange={setView} label="Transformation" options={[
          { value: "level", label: "Level" },
          { value: "pop", label: "Period change", disabled: !r.period_on_period?.allowed, title: r.period_on_period?.reason || r.period_on_period?.caveat },
          { value: "yoy", label: "Year change", disabled: !r.year_on_year?.allowed, title: r.year_on_year?.reason || r.year_on_year?.caveat },
          { value: "indexed", label: "Indexed", disabled: !r.index?.allowed, title: r.index?.reason },
        ]} />
        <span className="text-[10px] text-muted-foreground">
          {FREQ_LABEL[idn.frequency]} · {idn.seasonal_adjustment} · {idn.unit}
          {(from || to) && <> · range {from ?? "start"}–{to ?? "latest"}</>}
        </span>
      </div>
      {view !== "level" && (
        <p className="px-3 text-[10px] text-warning">
          {view === "pop" && (r.period_on_period?.caveat || a?.method.pop)}
          {view === "yoy" && (r.year_on_year?.caveat || a?.method.yoy)}
          {view === "indexed" && a?.method.indexed}
        </p>
      )}

      <div className="grid grid-cols-1 gap-2 px-3 pt-1 xl:grid-cols-[320px_minmax(0,1fr)]">
        <div className="space-y-2">
          <SelectedObservation d={d} a={a} point={selPoint} geoName={geoName} dimLabel={dimLabel} />
          <IdentityCard d={d} />
          <ProvenanceCard d={d} />
        </div>
        <div className="min-w-0 space-y-2">
          <Panel
            title={`${idn.title}${geoName ? ` · ${geoName}` : ""}${dimLabel && dim !== "_" ? ` · ${dimLabel}` : ""}`}
            subtitle={`${d.provenance.publisher} · ${d.provenance.dataset_identifier} · click a point to select the observation; amber dots = statistical outlier flags`}
            loading={analysis.isLoading} error={(analysis.error as Error | null)?.message} demo={demo}
            empty={a && !a.points.length ? "No observations in this range" : null}
          >
            <TimeSeriesChart series={chartSeries} unit={chartUnit} decimals={idn.decimals} height={300} zoom
              markers={markers} selected={selT} baseline={view === "pop" || view === "yoy" ? 0 : undefined}
              onPointClick={(_, p) => p.period && setParam({ period: p.period })} />
          </Panel>

          <Tabs value={tab} onValueChange={(v) => setParam({ tab: String(v) })}>
            <TabsList variant="line" className="flex-wrap">
              <TabsTrigger value="observations">Raw observations</TabsTrigger>
              <TabsTrigger value="statistics">Statistical context</TabsTrigger>
              <TabsTrigger value="comparisons">Comparisons</TabsTrigger>
              <TabsTrigger value="relationships">Relationships</TabsTrigger>
              <TabsTrigger value="revisions">Revisions {d.revision_count ? `(${d.revision_count})` : ""}</TabsTrigger>
              <TabsTrigger value="scenario">Scenario</TabsTrigger>
              <TabsTrigger value="findings">Findings</TabsTrigger>
              <TabsTrigger value="methodology">Methodology</TabsTrigger>
            </TabsList>
            <TabsContent value="observations"><ObservationsTab d={d} a={a} selected={selPeriod} onSelect={(p) => setParam({ period: p })} geo={geo} dim={dim} from={from} to={to} /></TabsContent>
            <TabsContent value="statistics"><StatisticsTab d={d} a={a} onSelect={(p) => setParam({ period: p })} /></TabsContent>
            <TabsContent value="comparisons"><ComparisonsTab d={d} a={a} geo={geo} dim={dim} onGeo={(g) => setParam({ geo: g, period: null })}
              onSeries={(id) => setParam({ series: id, geo: null, dim: null, period: null })} onDim={(x) => setParam({ dim: x, period: null })} /></TabsContent>
            <TabsContent value="relationships"><RelationshipsTab d={d} a={a} geo={geo} from={from} /></TabsContent>
            <TabsContent value="revisions"><RevisionsTab d={d} geo={geo} dim={dim} /></TabsContent>
            <TabsContent value="scenario"><ScenarioTab d={d} a={a} geo={geo} dim={dim} /></TabsContent>
            <TabsContent value="findings"><FindingsTab a={a} /></TabsContent>
            <TabsContent value="methodology"><MethodologyTab d={d} a={a} /></TabsContent>
          </Tabs>
        </div>
      </div>
    </div>
  );
}

const LEVEL_ORDER = (code: string) => (code === "K02000001" ? 0 : code.startsWith("K0") ? 1 : code.endsWith("92000001") || /^[WSN]92/.test(code) || code === "E92000001" ? 2 : code.startsWith("E12") ? 3 : 4);
function sortGeos(gs: { code: string; name: string }[]) {
  return [...gs].sort((a, b) => LEVEL_ORDER(a.code) - LEVEL_ORDER(b.code) || a.name.localeCompare(b.name));
}

function SeriesSwitch({ current, onChange }: { current: string; onChange: (id: string) => void }) {
  const { data } = useSeriesList();
  if (!data) return null;
  const cats = [...new Set(data.map((s) => s.category))];
  return (
    <label className="inline-flex items-center gap-1.5 text-[11px] text-muted-foreground">
      Metric
      <select value={current} onChange={(e) => onChange(e.target.value)}
        className="h-7 max-w-72 rounded border bg-secondary px-1.5 text-[11px] text-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring">
        {cats.map((c) => (
          <optgroup key={c} label={c.replace("_", " ")}>
            {data.filter((s) => s.category === c).map((s) => <option key={s.id} value={s.id}>{s.title}</option>)}
          </optgroup>
        ))}
      </select>
    </label>
  );
}

function SeriesPicker() {
  const { data, isLoading } = useSeriesList();
  const cats = [...new Set((data ?? []).map((s) => s.category))];
  return (
    <div className="p-3">
      <h1 className="text-[15px] font-semibold">Investigate</h1>
      <p className="mb-3 text-[11px] text-muted-foreground">Choose any metric to open its evidence workspace. You can also click any value elsewhere in the app.</p>
      {isLoading && <p className="text-xs text-muted-foreground">Loading catalogue…</p>}
      <div className="grid grid-cols-1 gap-2 md:grid-cols-2 xl:grid-cols-4">
        {cats.map((c) => (
          <Panel key={c} title={c.replace("_", " ").toUpperCase()}>
            <ul className="space-y-0.5">
              {(data ?? []).filter((s) => s.category === c).map((s) => (
                <li key={s.id} className="flex items-center gap-2 text-[11px]">
                  <StatusBadge status={s.status} reasons={s.status_reasons} compact />
                  <Link href={`/investigate?series=${s.id}`} className="min-w-0 flex-1 truncate hover:text-primary">{s.title}</Link>
                  <span className="tabular text-muted-foreground">{s.latest ? fmtValue(s.latest.value, s.unit, s.decimals) : "–"}</span>
                </li>
              ))}
            </ul>
          </Panel>
        ))}
      </div>
    </div>
  );
}
