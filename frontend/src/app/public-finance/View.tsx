"use client";
import { useQuery } from "@tanstack/react-query";
import { api, type SourceRow } from "@/lib/api";
import { fmtNumber } from "@/lib/format";
import { useSeriesList } from "@/lib/hooks";
import { DataTable } from "@/components/data/DataTable";
import { KpiTile } from "@/components/data/KpiTile";
import { Panel } from "@/components/data/Panel";
import { SeriesPanel } from "@/components/data/SeriesPanel";
import { StatusBadge } from "@/components/data/Status";
import { PageHeader } from "@/components/shell/PageHeader";

export function View() {
  const { data: list } = useSeriesList("public_finance");
  const gilts = useQuery({ queryKey: ["gilts"], queryFn: () => api<{ instruments: { name: string; isin: string; type: string; bracket: string; redemption: string; amount_m: number }[]; as_of: string | null; request_url: string | null }>("/gilts/instruments") });
  const { data: sources } = useQuery({ queryKey: ["sources"], queryFn: () => api<SourceRow[]>("/sources") });
  const dmo = sources?.find((s) => s.id === "dmo");
  return (
    <div className="pb-6">
      <PageHeader title="Public finance"
        description="Public sector borrowing and debt (ONS Public Sector Finances, sign conventions as published), gilt yields (BoE) and gilts in issue (DMO, where retrievable)." />
      <div className="grid grid-cols-2 gap-2 px-3 md:grid-cols-4">
        {(list ?? []).filter((s) => s.id !== "gilts_in_issue").map((s) => <KpiTile key={s.id} s={s} />)}
        {list?.find((s) => s.id === "gilts_in_issue") && <KpiTile s={list.find((s) => s.id === "gilts_in_issue")!} />}
      </div>
      <div className="mt-2 grid grid-cols-1 gap-2 px-3 xl:grid-cols-2">
        <SeriesPanel title="Public sector net borrowing (ex. banks), monthly" ids={["psnb_ex"]} kinds={["bar"]} unit="£m" defaultFrom="2019"
          subtitle="ONS J5II, NSA. As published, negative = net borrowing. Strongly seasonal: compare with the same month a year earlier." />
        <SeriesPanel title="Public sector net debt (ex. banks), % of GDP" ids={["psnd_ex_gdp"]} unit="% of GDP" defaultFrom="2000" />
        <SeriesPanel title="Public sector net debt (ex. banks), £bn" ids={["psnd_ex"]} unit="£bn" defaultFrom="2000" />
        <SeriesPanel title="Gilt yields" ids={["gilt_5y", "gilt_10y", "gilt_20y"]} names={["5-year", "10-year", "20-year"]} unit="%" decimals={2} defaultFrom="2019" />
      </div>
      <div className="mt-2 px-3">
        <Panel title="Gilts in issue (UK DMO, report D1A)" subtitle={gilts.data?.as_of ? `Close of business ${gilts.data.as_of}` : "Debt Management Office"}
          actions={dmo ? <StatusBadge status={dmo.status} reasons={dmo.status_reasons} /> : undefined}
          empty={gilts.data && !gilts.data.instruments.length ? (dmo?.last_error ? `Unavailable: ${dmo.last_error}. ${dmo.caveats[1] ?? ""}` : "Not retrieved yet") : null}>
          <DataTable rows={gilts.data?.instruments ?? []} rowKey={(r) => r.isin} maxHeight={360} initialSort={{ key: "r", dir: "asc" }}
            columns={[
              { key: "n", header: "Instrument", value: (r) => r.name },
              { key: "i", header: "ISIN", value: (r) => r.isin },
              { key: "t", header: "Type", value: (r) => r.type },
              { key: "b", header: "Maturity bracket", value: (r) => r.bracket },
              { key: "r", header: "Redemption", value: (r) => r.redemption },
              { key: "a", header: "Nominal in issue (£m)", align: "right", value: (r) => r.amount_m, render: (r) => fmtNumber(r.amount_m, 0) },
            ]} />
        </Panel>
      </div>
    </div>
  );
}
