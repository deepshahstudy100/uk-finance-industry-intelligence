"use client";
import { useQuery } from "@tanstack/react-query";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useMemo } from "react";
import { X } from "lucide-react";
import { api, qs } from "@/lib/api";
import { INK, seriesColor } from "@/lib/colors";
import { useFilters } from "@/lib/filters";
import { fmtNumber } from "@/lib/format";
import { useSeriesList } from "@/lib/hooks";
import { EChart } from "@/components/charts/EChart";
import { baseText, gridBase, tooltipBase } from "@/components/charts/theme";
import { TimeSeriesChart } from "@/components/charts/TimeSeriesChart";
import { Panel, Seg, Stat } from "@/components/data/Panel";
import { DemoBadge } from "@/components/data/Status";
import { PageHeader } from "@/components/shell/PageHeader";

type Mode = "level" | "indexed" | "yoy" | "pop";
interface CompareResp { mode: Mode; series: { series_id: string; title: string; unit: string; frequency: string; data_status: string; note: string | null; points: { period_start: string; value: number | null }[] }[] }
interface CorrResp {
  a: { id: string; title: string }; b: { id: string; title: string }; frequency: string; basis_description: string; aggregation: string;
  contemporaneous: { n: number; pearson: number | null; spearman: number | null; p_value: number | null; pearson_ci95?: number[] | null; start?: string; end?: string };
  lags: { lag: number; pearson: number | null; n: number }[]; best_lag: { lag: number; pearson: number | null } | null; lag_convention: string; warnings: string[];
}

export function View() {
  const sp = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const { filters } = useFilters();
  const ids = (sp.get("ids") ?? "cpi_yoy,bank_rate,awe_regular_growth").split(",").filter(Boolean).slice(0, 6);
  const mode = (sp.get("mode") as Mode) ?? "level";
  const basis = (sp.get("basis") as "changes" | "levels") ?? "changes";
  const setP = (patch: Record<string, string | null>) => {
    const n = new URLSearchParams(sp.toString());
    for (const [k, v] of Object.entries(patch)) (v ? n.set(k, v) : n.delete(k));
    router.replace(`${pathname}?${n.toString()}`, { scroll: false });
  };
  const { data: list } = useSeriesList();
  const cmp = useQuery({ queryKey: ["cmp", ids, mode, filters.from, filters.to, filters.geo],
    queryFn: () => api<CompareResp>(`/compare${qs({ ids: ids.join(","), mode, start: filters.from ?? "2010", end: filters.to, geo: filters.geo })}`) });
  const corr = useQuery({ queryKey: ["corr2", ids[0], ids[1], basis, filters.from], enabled: ids.length >= 2,
    queryFn: () => api<CorrResp>(`/correlate${qs({ a: ids[0], b: ids[1], basis, start: filters.from, max_lag: 12 })}`), retry: false });

  // One axis per unit: series with different units become small multiples (never a dual axis).
  const groups = useMemo(() => {
    const g = new Map<string, CompareResp["series"]>();
    for (const s of cmp.data?.series ?? []) g.set(s.unit, [...(g.get(s.unit) ?? []), s]);
    return [...g.entries()];
  }, [cmp.data]);
  const c = corr.data;
  const lagOpt = useMemo(() => c ? {
    animation: false, grid: { ...gridBase, top: 8 },
    tooltip: { ...tooltipBase, trigger: "axis" },
    xAxis: { type: "category", data: c.lags.map((l) => String(l.lag)), axisLabel: baseText, name: "lag", nameTextStyle: baseText },
    yAxis: { type: "value", min: -1, max: 1, axisLabel: baseText, splitLine: { lineStyle: { color: INK.grid } } },
    series: [{ type: "bar", barMaxWidth: 10, data: c.lags.map((l) => ({ value: l.pearson, itemStyle: { color: l.lag === c.best_lag?.lag ? "#e8a33d" : seriesColor(0), borderRadius: 2 } })) }],
  } : {}, [c]);

  return (
    <div className="pb-6">
      <PageHeader title="Compare & correlate"
        description="Overlay up to six indicators. Different units are split into small multiples or put on a common index - never a second y-axis. Correlation is computed on changes by default and is an association, not evidence of causation.">
        <Seg<Mode> value={mode} onChange={(m) => setP({ mode: m })} label="Mode" options={[
          { value: "level", label: "Levels" }, { value: "indexed", label: "Indexed (=100)" }, { value: "yoy", label: "Year-on-year" }, { value: "pop", label: "Period change" }]} />
      </PageHeader>
      <div className="flex flex-wrap items-center gap-1.5 px-3 pb-2">
        {ids.map((id, i) => (
          <span key={id} className="inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-[11px]">
            <span className="inline-block h-0.5 w-3" style={{ background: seriesColor(i) }} />
            {list?.find((s) => s.id === id)?.title ?? id}
            <button aria-label={`Remove ${id}`} onClick={() => setP({ ids: ids.filter((x) => x !== id).join(",") })}><X className="size-3" /></button>
          </span>
        ))}
        {ids.length < 6 && (
          <select value="" onChange={(e) => e.target.value && setP({ ids: [...ids, e.target.value].join(",") })} aria-label="Add series"
            className="h-7 rounded border bg-secondary px-1 text-[11px]">
            <option value="">+ Add indicator…</option>
            {(list ?? []).filter((s) => !ids.includes(s.id)).map((s) => <option key={s.id} value={s.id}>{s.title}</option>)}
          </select>
        )}
      </div>
      <div className="grid grid-cols-1 gap-2 px-3 xl:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
        <div className="space-y-2">
          {groups.map(([unit, ss]) => (
            <Panel key={unit} title={`${ss.map((s) => s.title).join(" · ")}`} subtitle={`Unit: ${unit}${ss.some((s) => s.note) ? ` · ${ss.map((s) => s.note).filter(Boolean).join(" ")}` : ""}`}
              loading={cmp.isLoading} demo={ss.some((s) => s.data_status === "demo")} actions={ss.some((s) => s.data_status === "demo") ? <DemoBadge /> : undefined}>
              <TimeSeriesChart height={groups.length > 1 ? 200 : 340} unit={unit.replace(" y/y", "")} group="cmp"
                series={ss.map((s) => ({ key: s.series_id, name: s.title, colorIndex: ids.indexOf(s.series_id), points: s.points.map((p) => ({ t: p.period_start, v: p.value })) }))} />
            </Panel>
          ))}
        </div>
        <Panel title={ids.length >= 2 ? `Correlation: ${c?.a.title ?? ids[0]} vs ${c?.b.title ?? ids[1]}` : "Correlation"} subtitle={c?.basis_description ?? "Uses the first two indicators"}
          loading={corr.isLoading} error={(corr.error as Error | null)?.message} empty={ids.length < 2 ? "Add a second indicator" : null}
          actions={<Seg value={basis} onChange={(b) => setP({ basis: b })} label="Basis" options={[{ value: "changes", label: "Changes" }, { value: "levels", label: "Levels" }]} />}>
          {c && (
            <>
              <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                <Stat label="Pearson r" value={fmtNumber(c.contemporaneous.pearson, 3)} sub={c.contemporaneous.pearson_ci95 ? `95% CI ${fmtNumber(c.contemporaneous.pearson_ci95[0], 2)}–${fmtNumber(c.contemporaneous.pearson_ci95[1], 2)}` : undefined} />
                <Stat label="Spearman ρ" value={fmtNumber(c.contemporaneous.spearman, 3)} />
                <Stat label="p (naïve)" value={c.contemporaneous.p_value != null ? c.contemporaneous.p_value.toExponential(1) : "–"} sub="overstated if autocorrelated" />
                <Stat label="n" value={c.contemporaneous.n} sub={`${c.frequency} · ${c.contemporaneous.start ?? ""}–${c.contemporaneous.end ?? ""}`} />
              </div>
              <EChart option={lagOpt} height={200} ariaLabel="Cross-correlation by lag" />
              <p className="text-[10px] text-muted-foreground">{c.lag_convention} {c.aggregation}</p>
              <ul className="mt-1 list-disc space-y-0.5 pl-4 text-[10px] text-warning">{c.warnings.map((w) => <li key={w}>{w}</li>)}</ul>
            </>
          )}
        </Panel>
      </div>
    </div>
  );
}
