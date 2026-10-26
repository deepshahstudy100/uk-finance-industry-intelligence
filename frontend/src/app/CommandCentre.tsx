"use client";
import { useState } from "react";
import { useOverview } from "@/lib/hooks";
import { KpiTile } from "@/components/data/KpiTile";
import { ScoreTile } from "@/components/data/EconomicScore";
import { IndustryHeatmap } from "@/components/data/IndustryHeatmap";
import { MarketMonitor } from "@/components/data/MarketMonitor";
import { AlertsPanel, EnergyNowPanel, SourceHealthPanel, TradePanel } from "@/components/data/MiscPanels";
import { RegionMapPanel } from "@/components/data/RegionMapPanel";
import { SeriesPanel } from "@/components/data/SeriesPanel";
import { PageHeader } from "@/components/shell/PageHeader";
import { Skeleton } from "@/components/ui/skeleton";

export function CommandCentre() {
  const { data, isLoading, error } = useOverview();
  const [metric, setMetric] = useState("claimant_rate");
  const [level, setLevel] = useState<"itl1" | "lad">("itl1");
  return (
    <div className="pb-6">
      <PageHeader
        title="Command centre"
        description="Headline UK indicators from official open sources. Every tile, point, cell and area opens the investigation workspace with its definition, raw observations and provenance."
      />
      {error && <p className="px-3 text-xs text-critical">API unreachable: {(error as Error).message}</p>}
      <div className="grid grid-cols-2 gap-2 px-3 sm:grid-cols-3 lg:grid-cols-4 2xl:grid-cols-6">
        <ScoreTile className="col-span-2" />
        {isLoading && Array.from({ length: 12 }).map((_, i) => <Skeleton key={i} className="h-[92px]" />)}
        {data?.kpis.map((k) => <KpiTile key={k.id} s={k} />)}
      </div>
      <div className="mt-2 grid grid-cols-1 gap-2 px-3 xl:grid-cols-3">
        <SeriesPanel
          className="xl:col-span-2"
          title="Macroeconomic timeline"
          subtitle="All series in % (single axis). CPI 12-month rate, Bank Rate, unemployment, GDP y/y, regular pay growth · ONS, BoE"
          ids={data?.timeline_series ?? ["cpi_yoy", "bank_rate", "unemployment_rate", "gdp_yoy", "awe_regular_growth"]}
          names={["CPI inflation", "Bank Rate", "Unemployment", "GDP y/y", "Regular pay growth"]}
          unit="%"
          height={270}
          defaultFrom="2015"
          group="macro"
        />
        {data && <MarketMonitor rows={data.markets} />}
      </div>
      <div className="mt-2 grid grid-cols-1 gap-2 px-3 xl:grid-cols-2">
        <IndustryHeatmap height={380} />
        <RegionMapPanel metric={metric} setMetric={setMetric} level={level} setLevel={setLevel} height={352} />
      </div>
      <div className="mt-2 grid grid-cols-1 gap-2 px-3 xl:grid-cols-3">
        <TradePanel height={250} />
        <EnergyNowPanel height={170} />
        <SeriesPanel title="House price inflation · UK HPI" ids={["hpi_yoy", "cpi_yoy"]} names={["House prices y/y", "CPI inflation"]}
          unit="%" height={250} defaultFrom="2015" subtitle="HM Land Registry UK HPI (NSA) and ONS CPI, both 12-month rates" />
      </div>
      <div className="mt-2 grid grid-cols-1 gap-2 px-3 xl:grid-cols-3">
        {data && <AlertsPanel alerts={data.alerts} className="xl:col-span-2" />}
        {data && <SourceHealthPanel sources={data.sources} />}
      </div>
    </div>
  );
}
