"use client";
import { useMemo } from "react";
import { useRouter } from "next/navigation";
import type { SeriesSummary } from "@/lib/api";
import { INK, seriesColor } from "@/lib/colors";
import { fmtValue } from "@/lib/format";
import { useInvestigate, useSeriesList } from "@/lib/hooks";
import { EChart } from "@/components/charts/EChart";
import { baseText, gridBase, tooltipBase } from "@/components/charts/theme";
import { KpiTile } from "@/components/data/KpiTile";
import { Panel } from "@/components/data/Panel";
import { SeriesPanel } from "@/components/data/SeriesPanel";
import { DemoBadge } from "@/components/data/Status";
import { PageHeader } from "@/components/shell/PageHeader";

const HEAD = ["gdp_qoq", "gdp_yoy", "gdp_monthly_index", "cpi_yoy", "cpih_yoy", "cpi_core_yoy", "unemployment_rate",
  "employment_rate", "inactivity_rate", "awe_total_growth", "awe_regular_growth", "vacancies", "hfce", "retail_sales_volume",
  "productivity_oph", "bank_rate"];

export function View() {
  const { data } = useSeriesList();
  const by = useMemo(() => new Map((data ?? []).map((s) => [s.id, s])), [data]);
  const tiles = HEAD.map((h) => by.get(h)).filter(Boolean) as SeriesSummary[];
  return (
    <div className="pb-6">
      <PageHeader title="National economic overview"
        description="Growth, prices, labour market, consumption and productivity. Current observation, its period and the previous value are shown on every tile; click to investigate." />
      <div className="grid grid-cols-2 gap-2 px-3 md:grid-cols-4 2xl:grid-cols-8">
        {tiles.map((s) => <KpiTile key={s.id} s={s} />)}
      </div>
      <div className="mt-2 grid grid-cols-1 gap-2 px-3 xl:grid-cols-2">
        <SeriesPanel title="GDP growth (quarter on quarter)" ids={["gdp_qoq"]} unit="%" kinds={["bar"]} defaultFrom="2010" group="macro" />
        <SeriesPanel title="Monthly GDP & sector indices" ids={["gdp_monthly_index", "iop_production", "ios_services"]}
          names={["Monthly GVA", "Production (B-E)", "Services"]} unit="index" defaultFrom="2018" group="macro" />
        <SeriesPanel title="Inflation: CPI, CPIH, core, goods, services (12-month rates)"
          ids={["cpi_yoy", "cpih_yoy", "cpi_core_yoy", "cpi_goods_yoy", "cpi_services_yoy"]}
          names={["CPI", "CPIH", "Core CPI", "Goods", "Services"]} unit="%" defaultFrom="2015" group="macro" />
        <CpiComponents />
        <SeriesPanel title="Labour market rates" ids={["unemployment_rate", "inactivity_rate"]} names={["Unemployment (16+)", "Inactivity (16-64)"]}
          unit="%" defaultFrom="2010" group="macro" subtitle="ONS Labour Force Survey, SA (rolling 3-month). Employment rate is on a different scale - see tile." />
        <SeriesPanel title="Nominal pay growth vs CPI inflation" ids={["awe_total_growth", "awe_regular_growth", "cpi_yoy"]}
          names={["Total pay (AWE)", "Regular pay (AWE)", "CPI inflation"]} unit="%" defaultFrom="2015" group="macro"
          subtitle="All % y/y. The gap is indicative only; ONS publishes official real-pay series separately." />
        <SeriesPanel title="Household consumption (CVM)" ids={["hfce"]} unit="£m" defaultFrom="2010" />
        <SeriesPanel title="Retail sales volume & productivity" ids={["retail_sales_volume"]} unit="index" defaultFrom="2015"
          subtitle="ONS retail sales index (volume, SA)" />
      </div>
    </div>
  );
}

/** Latest 12-month rate by COICOP division (published components; no contributions are inferred). */
function CpiComponents() {
  const router = useRouter();
  const inv = useInvestigate();
  const { data: list, isLoading } = useSeriesList("prices");
  const rows = (list ?? []).filter((s) => s.group === "cpi_divisions" && s.latest).map((s) => ({ id: s.id, label: s.title.replace(/^CPI \d+: /, ""), v: s.latest!.value as number, period: s.latest!.period, demo: s.data_status === "demo" }))
    .sort((a, b) => b.v - a.v);
  const option = useMemo(() => ({
    animation: false, grid: { ...gridBase, top: 4, bottom: 4 },
    tooltip: { ...tooltipBase, formatter: (p: { dataIndex: number }) => `${rows[p.dataIndex].label}<br/><b>${fmtValue(rows[p.dataIndex].v, "%", 1)}</b> (${rows[p.dataIndex].period})<br/><span style="color:${INK.muted};font-size:10px">Click to investigate</span>` },
    xAxis: { type: "value", axisLabel: { ...baseText, formatter: (v: number) => `${v}%` }, splitLine: { lineStyle: { color: INK.grid } } },
    yAxis: { type: "category", inverse: true, data: rows.map((r) => r.label.length > 34 ? r.label.slice(0, 33) + "…" : r.label), axisLabel: { ...baseText, color: INK.secondary }, axisTick: { show: false }, axisLine: { show: false } },
    series: [{ type: "bar", barMaxWidth: 12, data: rows.map((r) => ({ value: r.v, itemStyle: { color: r.v >= 0 ? seriesColor(0) : seriesColor(7), borderRadius: 2 } })),
      label: { show: true, position: "right", ...baseText, formatter: (p: { value: number }) => `${p.value.toFixed(1)}%` } }],
  }), [rows]);
  const demo = rows.some((r) => r.demo);
  return (
    <Panel title={`CPI by COICOP division · 12-month rate${rows[0] ? ` · ${rows[0].period}` : ""}`}
      subtitle="ONS MM23 published division rates. Contributions to the headline rate are a separate ONS table and are not derived here."
      demo={demo} actions={demo ? <DemoBadge /> : undefined} loading={isLoading} empty={rows.length ? null : "No data"}>
      <EChart option={option} height={260} onClick={(p) => { const r = rows[p.dataIndex ?? -1]; if (r) router.push(inv({ series: r.id, period: r.period })); }} />
    </Panel>
  );
}
