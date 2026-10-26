"use client";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { fmtChange, fmtCompact } from "@/lib/format";
import { useInvestigate } from "@/lib/hooks";
import { TimeSeriesChart } from "@/components/charts/TimeSeriesChart";
import { DataTable } from "@/components/data/DataTable";
import { Panel, Seg } from "@/components/data/Panel";
import { SeriesPanel } from "@/components/data/SeriesPanel";
import { TradePanel, useTrade } from "@/components/data/MiscPanels";
import { DemoBadge } from "@/components/data/Status";
import { PageHeader } from "@/components/shell/PageHeader";

export function View() {
  const [flow, setFlow] = useState<"exports" | "imports">("exports");
  const [by, setBy] = useState<"partner" | "sitc">("partner");
  const { data, isLoading } = useTrade(flow, by);
  const router = useRouter();
  const inv = useInvestigate();
  return (
    <div className="pb-6">
      <PageHeader title="Trade, prices & supply chains"
        description="ONS balance-of-payments totals (goods + services, SA) and HMRC Overseas Trade Statistics for goods by partner and SITC section (NSA, current prices). The two bases differ by design and are not mixed in one chart." />
      <div className="grid grid-cols-1 gap-2 px-3 xl:grid-cols-2">
        <SeriesPanel title="UK exports and imports (BoP basis, goods & services)" ids={["exports_total", "imports_total"]}
          names={["Exports", "Imports"]} unit="£m" defaultFrom="2016" group="trade" />
        <SeriesPanel title="Trade balance (BoP basis)" ids={["trade_balance"]} kinds={["bar"]} unit="£m" defaultFrom="2016" group="trade" />
        <TradePanel by="partner" top={15} height={330} />
        <TradePanel by="sitc" top={11} height={330} />
      </div>
      <div className="mt-2 grid grid-cols-1 gap-2 px-3 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <Panel title={`HMRC goods ${flow} by ${by === "partner" ? "partner" : "SITC section"} · 12 months to ${data?.window[1] ?? ""}`}
          subtitle={data?.note} loading={isLoading} demo={data?.data_status === "demo"}
          actions={<>
            {data?.data_status === "demo" && <DemoBadge />}
            <Seg value={by} onChange={setBy} label="By" options={[{ value: "partner", label: "Partner" }, { value: "sitc", label: "SITC" }]} />
            <Seg value={flow} onChange={setFlow} label="Flow" options={[{ value: "exports", label: "Exports" }, { value: "imports", label: "Imports" }]} />
          </>}>
          <DataTable rows={data?.rows ?? []} rowKey={(r) => r.dim} maxHeight={420} initialSort={{ key: "v", dir: "desc" }}
            onRowClick={(r) => data && router.push(inv({ series: data.series_id, dim: r.dim }))}
            columns={[
              { key: "l", header: by === "partner" ? "Partner" : "SITC section", value: (r) => r.label },
              { key: "d", header: "Code", value: (r) => r.dim },
              { key: "v", header: "Value (£)", align: "right", value: (r) => r.value, render: (r) => `£${fmtCompact(r.value)}` },
              { key: "s", header: "Share", align: "right", value: (r) => r.share_pct, render: (r) => `${r.share_pct.toFixed(1)}%` },
              { key: "c", header: "vs prior 12m", align: "right", value: (r) => r.change_pct, render: (r) => fmtChange(r.change_pct, "%", 1) },
            ]} />
        </Panel>
        <Panel title={`HMRC total goods ${flow}, monthly`} subtitle="Sum over all partners. Latest months are subject to revision." loading={isLoading}>
          <TimeSeriesChart height={300} unit="£" decimals={0} showLegend={false}
            series={[{ key: "t", name: `Goods ${flow}`, colorIndex: flow === "exports" ? 0 : 1, kind: "bar",
              points: (data?.monthly_total ?? []).map((p) => ({ t: `${p.period}-01`, v: p.value, period: p.period })) }]} />
        </Panel>
      </div>
    </div>
  );
}
