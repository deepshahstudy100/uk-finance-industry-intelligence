"use client";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { api } from "@/lib/api";
import { useFilters } from "@/lib/filters";
import { fmtChange, fmtNumber, fmtValue } from "@/lib/format";
import { useInvestigate, useSlice } from "@/lib/hooks";
import { Sparkline } from "@/components/charts/Sparkline";
import { DataTable } from "@/components/data/DataTable";
import { Panel } from "@/components/data/Panel";
import { MAP_METRICS, RegionMapPanel, useAreas } from "@/components/data/RegionMapPanel";
import { DemoBadge } from "@/components/data/Status";
import { PageHeader } from "@/components/shell/PageHeader";

interface Profile {
  geo: string; name: string; level: string | null; parent: string | null; children: { code: string; name: string }[];
  metrics: { series_id: string; title: string; unit: string; decimals: number; period: string; value: number; flags: Record<string, unknown>;
    uk_value: number | null; data_status: string; spark: number[] }[];
  industry_concentration: { section: string; name: string; enterprises: number; share_pct: number; uk_share_pct: number; location_quotient: number }[];
  lq_method: string;
}

export function View() {
  const { filters, set } = useFilters();
  const inv = useInvestigate();
  const [metric, setMetric] = useState("claimant_rate");
  const [level, setLevel] = useState<"itl1" | "lad">(filters.geo && !filters.geo.startsWith("E12") && !/^[KWSN]9|^K0|^E92/.test(filters.geo) ? "lad" : "itl1");
  const [period, setPeriod] = useState<string | null>(null);
  const geo = filters.geo ?? "K02000001";
  const m = MAP_METRICS.find((x) => x.id === metric)!;
  const profile = useQuery({ queryKey: ["region", geo], queryFn: () => api<Profile>(`/regions/profile/${geo}`) });
  const { data: areas } = useAreas();
  const effLevel = m.lad ? level : "itl1";
  const slice = useSlice(metric, { by: "geo", level: effLevel, period, dim: m.dim ? (filters.sector ?? "C") : undefined });
  const p = profile.data;
  const parent = p?.parent ? areas?.find((a) => a.code === p.parent) : null;
  const rows = (slice.data?.rows ?? []).filter((r) => effLevel === "itl1" || !filters.geo || !filters.geo.startsWith("E12") ||
    areas?.find((a) => a.code === r.geo)?.parent === filters.geo || r.geo === filters.geo);
  return (
    <div className="pb-6">
      <PageHeader title="Regional economic intelligence"
        description="England's regions, Scotland, Wales and Northern Ireland, with local-authority detail where the source publishes it (NOMIS). Click an area to select it; select a region then switch to LAs to drill down.">
        <nav aria-label="Geography breadcrumb" className="flex items-center gap-1 text-[11px]">
          <button onClick={() => { set({ geo: null }); setLevel("itl1"); }} className="text-cyan hover:underline">United Kingdom</button>
          {parent && parent.code !== "K02000001" && <><span>›</span><button onClick={() => set({ geo: parent.code })} className="text-cyan hover:underline">{parent.name}</button></>}
          {p && geo !== "K02000001" && <><span>›</span><b>{p.name}</b></>}
        </nav>
      </PageHeader>
      <div className="grid grid-cols-1 gap-2 px-3 xl:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)]">
        <RegionMapPanel metric={metric} setMetric={setMetric} level={level} setLevel={setLevel} height={520} period={period} setPeriod={setPeriod} />
        <div className="space-y-2">
          <Panel title={`Profile · ${p?.name ?? ""}`} subtitle="Latest published value for each regional series, with the UK figure for the same period" loading={profile.isLoading}
            empty={p && !p.metrics.length ? "No regional series published for this area" : null}>
            <table className="w-full text-[11px]">
              <thead className="text-muted-foreground"><tr className="border-b"><th className="py-1 text-left font-medium">Metric</th><th className="text-right font-medium">Value</th>
                <th className="text-right font-medium">UK</th><th className="text-right font-medium">Period</th><th className="pl-2 text-left font-medium">Trend</th></tr></thead>
              <tbody>
                {(p?.metrics ?? []).map((x) => (
                  <tr key={x.series_id} className="border-b border-border/50 hover:bg-accent/40">
                    <td className="py-1"><Link href={inv({ series: x.series_id, geo })} className="hover:text-primary">{x.title}</Link>
                      {typeof x.flags?.ci95_pp === "number" && <span className="ml-1 text-[9px] text-muted-foreground">±{x.flags.ci95_pp as number}pp</span>}
                      {typeof x.flags?.cv_pct === "number" && <span className="ml-1 text-[9px] text-muted-foreground">CV {x.flags.cv_pct as number}%</span>}
                      {x.data_status === "demo" && <DemoBadge className="ml-1" />}</td>
                    <td className="text-right tabular">{fmtValue(x.value, x.unit, x.decimals)}</td>
                    <td className="text-right tabular text-muted-foreground">{fmtValue(x.uk_value, x.unit, x.decimals)}</td>
                    <td className="text-right tabular text-muted-foreground">{x.period}</td>
                    <td className="pl-2"><Sparkline values={x.spark} width={64} height={16} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Panel>
          {p && p.industry_concentration.length > 0 && (
            <Panel title="Industrial concentration (location quotients)" subtitle={p.lq_method}>
              <DataTable rows={p.industry_concentration} rowKey={(r) => r.section} maxHeight={220} initialSort={{ key: "lq", dir: "desc" }}
                onRowClick={(r) => set({ sector: r.section })}
                columns={[
                  { key: "s", header: "SIC", value: (r) => r.section },
                  { key: "n", header: "Industry", value: (r) => r.name },
                  { key: "e", header: "Enterprises", align: "right", value: (r) => r.enterprises, render: (r) => fmtNumber(r.enterprises, 0) },
                  { key: "sh", header: "Share", align: "right", value: (r) => r.share_pct, render: (r) => `${r.share_pct.toFixed(1)}%` },
                  { key: "uk", header: "UK share", align: "right", value: (r) => r.uk_share_pct, render: (r) => `${r.uk_share_pct.toFixed(1)}%` },
                  { key: "lq", header: "LQ", align: "right", value: (r) => r.location_quotient, render: (r) => <span className={r.location_quotient > 1.2 ? "text-primary" : ""}>{r.location_quotient.toFixed(2)}</span> },
                ]} />
            </Panel>
          )}
          {p && p.children.length > 0 && (
            <Panel title={`Local authorities in ${p.name} (${p.children.length})`} subtitle="ONS LAD25 → ITL1 lookup">
              <div className="flex max-h-40 flex-wrap gap-1 overflow-auto">
                {p.children.map((c) => (
                  <button key={c.code} onClick={() => { set({ geo: c.code }); setLevel("lad"); }}
                    className="rounded border px-1.5 py-0.5 text-[10px] hover:border-primary/60 hover:text-primary">{c.name}</button>
                ))}
              </div>
            </Panel>
          )}
        </div>
      </div>
      <div className="mt-2 px-3">
        <Panel title={`Ranking · ${m.label} · ${slice.data?.period ?? ""}`} subtitle={slice.data?.share_note ?? "Sortable; click a row to select the area. Change is vs the previous published period."}
          loading={slice.isLoading} demo={slice.data?.data_status === "demo"}>
          <DataTable rows={rows} rowKey={(r) => r.geo} selectedKey={filters.geo} onRowClick={(r) => set({ geo: r.geo })} maxHeight={360}
            initialSort={{ key: "v", dir: "desc" }}
            columns={[
              { key: "n", header: "Area", value: (r) => r.geo_name },
              { key: "c", header: "Code", value: (r) => r.geo },
              { key: "v", header: m.unit, align: "right", value: (r) => r.value, render: (r) => fmtValue(r.value, m.unit, m.d, false) },
              { key: "ch", header: `Change (${slice.data?.change_unit ?? ""})`, align: "right", value: (r) => r.change, render: (r) => fmtChange(r.change, slice.data?.change_unit ?? "%") },
              { key: "u", header: "Uncertainty", value: (r) => Number(r.flags?.ci95_pp ?? r.flags?.cv_pct ?? NaN),
                render: (r) => r.flags?.ci95_pp != null ? `±${r.flags.ci95_pp}pp` : r.flags?.cv_pct != null ? `CV ${r.flags.cv_pct}%${r.flags.reliability ? " ⚠" : ""}` : "–" },
              { key: "go", header: "", value: () => "", render: (r) => <Link onClick={(e) => e.stopPropagation()} href={inv({ series: metric, geo: r.geo, dim: m.dim ? (filters.sector ?? "C") : undefined, period: slice.data?.period })} className="text-cyan hover:underline">investigate</Link> },
            ]} />
        </Panel>
      </div>
    </div>
  );
}
