"use client";
import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { ExternalLink } from "lucide-react";
import { api } from "@/lib/api";
import { INK, seriesColor } from "@/lib/colors";
import { useFilters } from "@/lib/filters";
import { fmtValue } from "@/lib/format";
import { useInvestigate, useSlice } from "@/lib/hooks";
import { EChart } from "@/components/charts/EChart";
import { baseText, gridBase, tooltipBase } from "@/components/charts/theme";
import { DataTable } from "@/components/data/DataTable";
import { NativeSelect, Panel } from "@/components/data/Panel";
import { SeriesPanel } from "@/components/data/SeriesPanel";
import { DemoBadge } from "@/components/data/Status";
import { PageHeader } from "@/components/shell/PageHeader";

interface PPD {
  district: string; since: string; count: number; median_price: number | null; query: string; source_page_url: string;
  attribution: string; note: string;
  rows: { transaction_uri: string; price: number; date: string; postcode: string; property_type: string; estate_type: string; new_build: boolean; category: string }[];
}

export function View() {
  const { filters } = useFilters();
  const router = useRouter();
  const inv = useInvestigate();
  const slice = useSlice("hpi_avg_price", { by: "geo", level: "itl1" });
  const rows = (slice.data?.rows ?? []).filter((r) => r.value != null).sort((a, b) => (b.value ?? 0) - (a.value ?? 0));
  const option = useMemo(() => ({
    animation: false, grid: { ...gridBase, top: 4, bottom: 4 },
    tooltip: { ...tooltipBase, formatter: (p: { dataIndex: number }) => `${rows[p.dataIndex].geo_name}<br/><b>${fmtValue(rows[p.dataIndex].value, "£", 0, false)}</b><br/>${slice.data?.period}` },
    xAxis: { type: "value", axisLabel: { ...baseText, formatter: (v: number) => `£${Math.round(v / 1000)}k` }, splitLine: { lineStyle: { color: INK.grid } } },
    yAxis: { type: "category", inverse: true, data: rows.map((r) => r.geo_name), axisLabel: { ...baseText, color: INK.secondary }, axisLine: { show: false }, axisTick: { show: false } },
    series: [{ type: "bar", barMaxWidth: 12, data: rows.map((r) => ({ value: r.value, itemStyle: { color: r.geo === filters.geo ? "#e8a33d" : seriesColor(0), borderRadius: [0, 3, 3, 0] } })) }],
  }), [rows, slice.data, filters.geo]);
  const geoSeries = filters.geo && rows.some((r) => r.geo === filters.geo) ? filters.geo : null;
  return (
    <div className="pb-6">
      <PageHeader title="Housing"
        description="UK House Price Index (HM Land Registry, monthly, NSA, recent months provisional), mortgage approvals and quoted rates (BoE), and individual Price Paid transactions on demand." />
      <div className="grid grid-cols-1 gap-2 px-3 xl:grid-cols-2">
        <Panel title={`Average house price by region · ${slice.data?.period ?? ""}`} subtitle="UK HPI, all property types. Click a bar to investigate." loading={slice.isLoading}
          demo={slice.data?.data_status === "demo"} actions={slice.data?.data_status === "demo" ? <DemoBadge /> : undefined}>
          <EChart option={option} height={300} onClick={(p) => { const r = rows[p.dataIndex ?? -1]; if (r) router.push(inv({ series: "hpi_avg_price", geo: r.geo, period: slice.data?.period })); }} />
        </Panel>
        <SeriesPanel title={`House price inflation${geoSeries ? "" : " · UK"}`} ids={["hpi_yoy"]} geo={geoSeries ?? undefined} unit="%" defaultFrom="2010"
          subtitle="UK HPI annual % change as published. Use the global geography filter to switch region." />
        <SeriesPanel title="Mortgage approvals for house purchase" ids={["mortgage_approvals"]} kinds={["bar"]} unit="number" decimals={0} defaultFrom="2015" />
        <SeriesPanel title="Quoted mortgage rates vs Bank Rate" ids={["mortgage_2y_75", "mortgage_5y_75", "bank_rate"]} names={["2y fixed 75% LTV", "5y fixed 75% LTV", "Bank Rate"]}
          unit="%" decimals={2} defaultFrom="2015" />
      </div>
      <div className="mt-2 px-3"><PricePaid /></div>
    </div>
  );
}

const DISTRICTS = ["MANCHESTER", "BIRMINGHAM", "LEEDS", "BRISTOL", "CITY OF WESTMINSTER", "CARDIFF", "NEWCASTLE UPON TYNE", "LIVERPOOL", "SHEFFIELD", "NOTTINGHAM"];

function PricePaid() {
  const [district, setDistrict] = useState("MANCHESTER");
  const [input, setInput] = useState("MANCHESTER");
  const [months, setMonths] = useState("6");
  const q = useQuery({
    queryKey: ["ppd", district, months],
    queryFn: () => api<PPD>(`/housing/transactions?district=${encodeURIComponent(district)}&months=${months}&limit=300`),
    staleTime: 6 * 3600_000,
  });
  return (
    <Panel title={`Price Paid transactions · ${district}`} subtitle={q.data ? `${q.data.count} transactions since ${q.data.since} · median of returned rows ${fmtValue(q.data.median_price, "£", 0, false)} · ${q.data.note}` : "HM Land Registry Price Paid Data (queried live via SPARQL, cached)"}
      loading={q.isLoading} error={(q.error as Error | null)?.message}
      actions={<>
        <form onSubmit={(e) => { e.preventDefault(); setDistrict(input.trim().toUpperCase()); }} className="flex items-center gap-1">
          <input list="districts" value={input} onChange={(e) => setInput(e.target.value)} aria-label="Local authority district"
            className="h-7 w-48 rounded border bg-secondary px-1.5 text-[11px] uppercase outline-none focus-visible:ring-2 focus-visible:ring-ring" />
          <datalist id="districts">{DISTRICTS.map((d) => <option key={d} value={d} />)}</datalist>
          <button className="h-7 rounded border border-primary/50 px-2 text-[11px] text-primary hover:bg-primary/10">Query</button>
        </form>
        <NativeSelect label="Window" value={months} onChange={setMonths} options={["3", "6", "12"].map((m) => ({ value: m, label: `${m} months` }))} />
      </>}>
      <DataTable rows={q.data?.rows ?? []} rowKey={(r) => r.transaction_uri} maxHeight={380} initialSort={{ key: "d", dir: "desc" }}
        columns={[
          { key: "d", header: "Date", value: (r) => r.date },
          { key: "p", header: "Price", align: "right", value: (r) => r.price, render: (r) => fmtValue(r.price, "£", 0, false) },
          { key: "pc", header: "Postcode", value: (r) => r.postcode },
          { key: "t", header: "Type", value: (r) => r.property_type },
          { key: "e", header: "Tenure", value: (r) => r.estate_type },
          { key: "n", header: "New build", value: (r) => (r.new_build ? "yes" : "no") },
          { key: "c", header: "Category", value: (r) => r.category.replace("PricePaidTransaction", "") },
          { key: "src", header: "Source record", value: (r) => r.transaction_uri,
            render: (r) => <a href={r.transaction_uri} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-cyan hover:underline">record <ExternalLink className="size-3" /></a> },
        ]} />
      {q.data && <details className="mt-1 text-[10px] text-muted-foreground"><summary className="cursor-pointer">SPARQL query & attribution</summary><pre className="mt-1 overflow-auto whitespace-pre-wrap rounded bg-secondary p-2">{q.data.query}</pre>{q.data.attribution}</details>}
    </Panel>
  );
}
