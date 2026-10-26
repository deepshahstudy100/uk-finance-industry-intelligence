"use client";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { AlertTriangle, Info, OctagonAlert } from "lucide-react";
import { api, type AlertItem, type ObservationsResponse } from "@/lib/api";
import { INK, seriesColor, STATUS_COLOR } from "@/lib/colors";
import { ago, fmtChange, fmtCompact, fmtValue, LATENCY_LABEL } from "@/lib/format";
import { useInvestigate } from "@/lib/hooks";
import { EChart } from "@/components/charts/EChart";
import { baseText, gridBase, tooltipBase } from "@/components/charts/theme";
import { TimeSeriesChart } from "@/components/charts/TimeSeriesChart";
import { Panel, Seg } from "./Panel";
import { DemoBadge, StatusBadge } from "./Status";

const SEV_ICON = { info: Info, warning: AlertTriangle, critical: OctagonAlert };
const SEV_COLOR = { info: "#3fb6d3", warning: STATUS_COLOR.delayed, critical: STATUS_COLOR.unavailable };

export function AlertsPanel({ alerts, className, title = "Anomaly & data alerts" }: {
  alerts: AlertItem[]; className?: string; title?: string;
}) {
  const inv = useInvestigate();
  return (
    <Panel title={title} subtitle="Statistical flags, revisions, failures and stale data. Flags are prompts to check, not conclusions."
      className={className} empty={alerts.length ? null : "No active alerts"}>
      <ul className="max-h-72 space-y-1 overflow-auto pr-1">
        {alerts.map((a) => {
          const Icon = SEV_ICON[a.severity] ?? Info;
          const body = (
            <div className="flex gap-2 rounded border border-border/60 bg-secondary/40 px-2 py-1.5 hover:bg-accent/50">
              <Icon className="mt-0.5 size-3.5 shrink-0" style={{ color: SEV_COLOR[a.severity] }} aria-label={a.severity} />
              <div className="min-w-0">
                <div className="flex items-center gap-2 text-[11px] font-medium">
                  <span className="truncate">{a.title}</span>
                  <span className="shrink-0 rounded-sm border px-1 text-[9px] uppercase text-muted-foreground">{a.kind}</span>
                </div>
                <div className="line-clamp-2 text-[10px] text-muted-foreground">{a.detail}</div>
                <div className="text-[9px] text-muted-foreground">{ago(a.updated_at)}{a.period ? ` · ${a.period}` : ""}</div>
              </div>
            </div>
          );
          return (
            <li key={a.id}>
              {a.series_id ? <Link href={inv({ series: a.series_id, geo: a.geo, dim: a.dim, period: a.period })}>{body}</Link>
                : <Link href="/sources">{body}</Link>}
            </li>
          );
        })}
      </ul>
    </Panel>
  );
}

export function SourceHealthPanel({ sources, className }: {
  sources: { id: string; name: string; publisher: string; status: string; last_success_at: string | null; latency_class: string }[];
  className?: string;
}) {
  return (
    <Panel title="Source health" subtitle="Status relative to each source's own schedule" className={className}>
      <ul className="divide-y divide-border/60">
        {sources.map((s) => (
          <li key={s.id} className="flex items-center gap-2 py-1 text-[11px]">
            <StatusBadge status={s.status} compact />
            <Link href={`/sources#${s.id}`} className="min-w-0 flex-1 truncate hover:text-primary">{s.publisher}</Link>
            <span className="hidden text-[10px] text-muted-foreground xl:inline">{LATENCY_LABEL[s.latency_class]}</span>
            <span className="w-20 text-right text-[10px] text-muted-foreground tabular">{ago(s.last_success_at)}</span>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

interface TradeResp {
  series_id: string; flow: string; window: [string, string]; previous_window: [string, string] | null; total: number;
  rows: { dim: string; label: string; value: number; share_pct: number; change_pct: number | null }[];
  monthly_total: { period: string; value: number }[]; data_status: "real" | "demo"; note: string;
}

export function useTrade(flow: string, by: "partner" | "sitc") {
  return useQuery({ queryKey: ["trade", flow, by], queryFn: () => api<TradeResp>(`/trade/partners?flow=${flow}&by=${by}&months=12`) });
}

/** Top partners / SITC sections over the latest 12 months (HMRC OTS). Bars are sorted; click opens the series. */
export function TradePanel({ className, top = 10, by = "partner", height = 260 }: {
  className?: string; top?: number; by?: "partner" | "sitc"; height?: number;
}) {
  const [flow, setFlow] = useState<"exports" | "imports">("exports");
  const { data, isLoading, error } = useTrade(flow, by);
  const router = useRouter();
  const inv = useInvestigate();
  const rows = (data?.rows ?? []).slice(0, top);
  const option = useMemo(() => ({
    animation: false,
    grid: { ...gridBase, left: 4, top: 4, bottom: 4 },
    tooltip: { ...tooltipBase, formatter: (p: { dataIndex: number }) => {
      const r = rows[p.dataIndex];
      return `<div style="font-size:11px"><b>${r.label}</b><br/>£${fmtCompact(r.value)} (${r.share_pct.toFixed(1)}% of total)<br/>
        ${r.change_pct != null ? `${fmtChange(r.change_pct, "%")} vs previous 12 months` : "No comparable prior window"}</div>`;
    } },
    xAxis: { type: "value", axisLabel: { ...baseText, formatter: (v: number) => `£${fmtCompact(v)}` },
      splitLine: { lineStyle: { color: INK.grid } } },
    yAxis: { type: "category", inverse: true, data: rows.map((r) => r.label.length > 28 ? r.label.slice(0, 27) + "…" : r.label),
      axisLabel: { ...baseText, color: INK.secondary }, axisLine: { show: false }, axisTick: { show: false } },
    series: [{ type: "bar", data: rows.map((r) => r.value), barMaxWidth: 12,
      itemStyle: { color: seriesColor(flow === "exports" ? 0 : 1), borderRadius: [0, 3, 3, 0] },
      label: { show: true, position: "right", ...baseText, formatter: (p: { dataIndex: number }) => `${rows[p.dataIndex].share_pct.toFixed(1)}%` } }],
  }), [rows, flow]);
  return (
    <Panel title={`UK goods trade by ${by === "partner" ? "partner country" : "SITC section"} · last 12 months`}
      subtitle={data ? `HMRC OTS · ${data.window[0]}–${data.window[1]} · total £${fmtCompact(data.total)} · goods, current prices, NSA` : "HMRC Overseas Trade Statistics"}
      className={className} loading={isLoading} error={(error as Error | null)?.message} demo={data?.data_status === "demo"}
      investigate={data ? inv({ series: data.series_id, dim: rows[0]?.dim }) : undefined}
      actions={<>
        {data?.data_status === "demo" && <DemoBadge />}
        <Seg value={flow} onChange={setFlow} label="Flow" options={[{ value: "exports", label: "Exports" }, { value: "imports", label: "Imports" }]} />
      </>}>
      <EChart option={option} height={height} ariaLabel="Bar chart of trade by partner"
        onClick={(p) => { const r = rows[p.dataIndex ?? -1]; if (r && data) router.push(inv({ series: data.series_id, dim: r.dim })); }} />
    </Panel>
  );
}

const FUEL_GROUPS: { key: string; label: string; fuels: string[] }[] = [
  { key: "wind", label: "Wind", fuels: ["wind"] },
  { key: "gas", label: "Gas", fuels: ["gas"] },
  { key: "nuclear", label: "Nuclear", fuels: ["nuclear"] },
  { key: "imports", label: "Imports", fuels: ["imports"] },
  { key: "biomass", label: "Biomass", fuels: ["biomass"] },
  { key: "solar", label: "Solar", fuels: ["solar"] },
  { key: "other", label: "Other (hydro, coal, other)", fuels: ["hydro", "coal", "other"] },
];

/** GB generation mix (stacked shares, 7 groups - fewer than the 8 categorical slots) + carbon intensity. */
export function EnergyNowPanel({ className, height = 200 }: { className?: string; height?: number }) {
  const router = useRouter();
  const inv = useInvestigate();
  const mix = useQuery({ queryKey: ["mix"], queryFn: async () => {
    const out = await Promise.all(FUEL_GROUPS.flatMap((g) => g.fuels).map((f) =>
      api<ObservationsResponse>(`/series/generation_mix/observations?geo=K03000001&dim=${f}`)));
    return out;
  }, refetchInterval: 30 * 60_000 });
  const ci = useQuery({ queryKey: ["ci"], queryFn: () => api<ObservationsResponse>("/series/carbon_intensity/observations?geo=K03000001"),
    refetchInterval: 30 * 60_000 });
  const series = useMemo(() => {
    if (!mix.data) return [];
    const byFuel = new Map(mix.data.map((r) => [r.dim, r.observations]));
    return FUEL_GROUPS.map((g, i) => {
      const acc = new Map<string, { t: string; v: number; period: string }>();
      for (const f of g.fuels) for (const o of byFuel.get(f) ?? []) {
        const cur = acc.get(o.period) ?? { t: o.period.replace("Z", ":00Z"), v: 0, period: o.period };
        cur.v += o.value ?? 0;
        acc.set(o.period, cur);
      }
      return { key: g.key, name: g.label, kind: "area" as const, stack: "mix", colorIndex: i,
        points: [...acc.values()].sort((a, b) => a.period.localeCompare(b.period)) };
    });
  }, [mix.data]);
  const last = ci.data?.observations.at(-1);
  const demo = mix.data?.some((r) => r.data_status === "demo") || ci.data?.data_status === "demo";
  return (
    <Panel title="GB electricity: generation mix & carbon intensity (7 days)" className={className}
      subtitle={`NESO Carbon Intensity API (CC BY 4.0) · half-hourly modelled estimates · latest ${last?.period ?? "–"}`}
      loading={mix.isLoading} error={(mix.error as Error | null)?.message} demo={demo}
      investigate={inv({ series: "generation_mix", geo: "K03000001", dim: "wind" })}
      actions={<>
        {demo && <DemoBadge />}
        {last && <span className="text-[11px] tabular">{fmtValue(last.value, "gCO2/kWh")}
          <span className="ml-1 text-[10px] text-muted-foreground">{String(last.flags?.index ?? "")}{last.status === "forecast" ? " (forecast)" : ""}</span></span>}
      </>}>
      <TimeSeriesChart series={series} unit="% of generation" decimals={1} height={height} yMin={0} yMax={100}
        onPointClick={(key) => router.push(inv({ series: "generation_mix", geo: "K03000001", dim: key === "other" ? "other" : key }))} />
      {ci.data && (
        <TimeSeriesChart height={90} unit="gCO2/kWh" decimals={0} showLegend={false}
          series={[{ key: "ci", name: "Carbon intensity", points: ci.data.observations.map((o) => ({ t: o.period.replace("Z", ":00Z"), v: o.value, period: o.period })), colorIndex: 6 }]}
          onPointClick={(_, p) => router.push(inv({ series: "carbon_intensity", geo: "K03000001", period: p.period }))} />
      )}
    </Panel>
  );
}
