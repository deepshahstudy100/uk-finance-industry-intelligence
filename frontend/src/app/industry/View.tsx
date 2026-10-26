"use client";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { api, type SeriesSummary } from "@/lib/api";
import { useFilters } from "@/lib/filters";
import { fmtChange, fmtCompact, fmtValue } from "@/lib/format";
import { useInvestigate } from "@/lib/hooks";
import { DataTable } from "@/components/data/DataTable";
import { IndustryHeatmap, useHeatmap } from "@/components/data/IndustryHeatmap";
import { Panel } from "@/components/data/Panel";
import { RegionMapPanel } from "@/components/data/RegionMapPanel";
import { SeriesPanel } from "@/components/data/SeriesPanel";
import { StatusBadge } from "@/components/data/Status";
import { PageHeader } from "@/components/shell/PageHeader";

interface Profile {
  section: string; name: string; classification: string; note: string;
  metrics: (SeriesSummary & { kind: string; dim?: string; value?: number; period?: string; change_pct?: number | null })[];
}

export function View() {
  const { filters, set } = useFilters();
  const sector = filters.sector ?? "C";
  const router = useRouter();
  const inv = useInvestigate();
  const yoy = useHeatmap("yoy", 13);
  const m3 = useHeatmap("3m3m", 3);
  const [level, setLevel] = useState<"itl1" | "lad">("itl1");
  const [metric, setMetric] = useState("business_counts");
  const profile = useQuery({ queryKey: ["industry", sector, filters.geo], queryFn: () => api<Profile>(`/industry/${sector}${filters.geo ? `?geo=${filters.geo}` : ""}`) });
  const rows = useMemo(() => (yoy.data?.rows ?? []).map((r) => {
    const last = r.cells.at(-1);
    const m = m3.data?.rows.find((x) => x.section === r.section)?.cells.at(-1);
    return { ...r, period: last?.period, level: last?.level, yoy: last?.value ?? null, m3: m?.value ?? null,
      jobs: r.workforce_jobs?.value ?? null, ent: r.enterprises?.value ?? null };
  }), [yoy.data, m3.data]);
  const totalJobs = rows.reduce((s, r) => s + (r.jobs ?? 0), 0);
  const sel = rows.find((r) => r.section === sector);
  return (
    <div className="pb-6">
      <PageHeader title="Industry intelligence"
        description="Output (ONS monthly GDP), employment (workforce jobs) and business counts (IDBR) by SIC 2007 section. Click a heatmap row or table row to focus a sector; it filters the map and profile." />
      <div className="grid grid-cols-1 gap-2 px-3 xl:grid-cols-[minmax(0,1.25fr)_minmax(0,1fr)]">
        <IndustryHeatmap height={420} months={18} onSelectSector={(s) => set({ sector: s })} />
        <Panel title={`Sector profile · ${sector}: ${profile.data?.name ?? ""}`} subtitle={profile.data?.note} loading={profile.isLoading}
          investigate={sel ? inv({ series: sel.series_id }) : undefined}>
          <ul className="divide-y divide-border/60">
            {(profile.data?.metrics ?? []).map((m) => (
              <li key={(m.id ?? "") + (m.dim ?? "")} className="flex items-center gap-2 py-1.5 text-[11px]">
                {m.kind === "series" && <StatusBadge status={m.status} reasons={m.status_reasons} compact />}
                <Link href={inv({ series: m.id, dim: m.dim, geo: m.kind === "dim" ? filters.geo : undefined })} className="min-w-0 flex-1 truncate hover:text-primary">{m.title}</Link>
                <span className="tabular">{m.kind === "series" ? fmtValue(m.latest?.value, m.unit, m.decimals) : fmtCompact(m.value)}</span>
                <span className="w-16 text-right text-[10px] text-muted-foreground tabular">{m.kind === "series" ? m.latest?.period : m.period}</span>
                <span className="w-16 text-right text-[10px] tabular">{m.kind === "series" ? fmtChange(m.change?.value, m.change?.unit ?? "%") : fmtChange(m.change_pct, "%")}</span>
              </li>
            ))}
          </ul>
          <SeriesPanel className="mt-2 border-0" title={`Output index · section ${sector}`} ids={[`gva_${sector}`]} unit="index" height={170} defaultFrom="2018" />
        </Panel>
      </div>
      <div className="mt-2 grid grid-cols-1 gap-2 px-3 xl:grid-cols-[minmax(0,1.25fr)_minmax(0,1fr)]">
        <Panel title="Industries compared" subtitle={`Latest month ${rows[0]?.period ?? ""}. Jobs: workforce jobs (SA, latest quarter). Enterprises: UK Business Counts (March). Shares are of the listed sections.`}
          loading={yoy.isLoading}>
          <DataTable rows={rows} rowKey={(r) => r.section} selectedKey={sector} onRowClick={(r) => set({ sector: r.section })} maxHeight={420}
            initialSort={{ key: "yoy", dir: "desc" }}
            columns={[
              { key: "s", header: "SIC", value: (r) => r.section },
              { key: "n", header: "Industry", value: (r) => r.name },
              { key: "level", header: "Output index", align: "right", value: (r) => r.level, render: (r) => fmtValue(r.level, "index", 1) },
              { key: "yoy", header: "y/y", align: "right", value: (r) => r.yoy, render: (r) => fmtChange(r.yoy, "%", 1) },
              { key: "m3", header: "3m/3m", align: "right", value: (r) => r.m3, render: (r) => fmtChange(r.m3, "%", 1) },
              { key: "jobs", header: "Jobs", align: "right", value: (r) => r.jobs, render: (r) => fmtCompact(r.jobs) },
              { key: "js", header: "Jobs share", align: "right", value: (r) => (r.jobs ?? 0) / (totalJobs || 1), render: (r) => r.jobs ? `${((r.jobs / totalJobs) * 100).toFixed(1)}%` : "–" },
              { key: "ent", header: "Enterprises", align: "right", value: (r) => r.ent, render: (r) => fmtCompact(r.ent) },
              { key: "go", header: "", value: () => "", render: (r) => <button onClick={(e) => { e.stopPropagation(); router.push(inv({ series: r.series_id })); }} className="text-cyan hover:underline">investigate</button> },
            ]} />
        </Panel>
        <RegionMapPanel metric={metric} setMetric={setMetric} level={level} setLevel={setLevel} height={400} />
      </div>
    </div>
  );
}
