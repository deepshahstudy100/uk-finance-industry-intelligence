"use client";
import { useOverview } from "@/lib/hooks";
import { MarketMonitor } from "@/components/data/MarketMonitor";
import { Panel } from "@/components/data/Panel";
import { SeriesPanel } from "@/components/data/SeriesPanel";
import { PageHeader } from "@/components/shell/PageHeader";

export function View() {
  const { data } = useOverview();
  return (
    <div className="pb-6">
      <PageHeader title="Financial & market monitor"
        description="Policy rate, money-market rate, gilt yields, mortgage rates and sterling. Timing is labelled on every row: Bank of England end-of-day estimates (published next business day) and ECB reference rates. No real-time prices are claimed." />
      <div className="grid grid-cols-1 gap-2 px-3 xl:grid-cols-[minmax(0,1fr)_420px]">
        <div className="grid grid-cols-1 gap-2">
          <SeriesPanel title="Policy & market rates" ids={["bank_rate", "sonia", "gilt_5y", "gilt_10y", "gilt_20y"]}
            names={["Bank Rate", "SONIA", "5y gilt", "10y gilt", "20y gilt"]} unit="%" decimals={2} height={280} defaultFrom="2019" group="mkts"
            subtitle="Bank of England IADB · gilt yields are BoE nominal par yield-curve estimates (end of day)" />
          <div className="grid grid-cols-1 gap-2 lg:grid-cols-3">
            <SeriesPanel title="GBP/USD" ids={["fx_gbp_usd"]} unit="USD per GBP" decimals={4} defaultFrom="2019" group="mkts"
              subtitle="Derived from ECB reference rates (USD/EUR ÷ GBP/EUR)" />
            <SeriesPanel title="GBP/EUR" ids={["fx_gbp_eur"]} unit="EUR per GBP" decimals={4} defaultFrom="2019" group="mkts"
              subtitle="Derived: 1 ÷ ECB GBP-per-EUR reference rate" />
            <SeriesPanel title="GBP/JPY" ids={["fx_gbp_jpy"]} unit="JPY per GBP" decimals={2} defaultFrom="2019" group="mkts"
              subtitle="Derived from ECB reference rates (cross)" />
          </div>
          <SeriesPanel title="Quoted mortgage rates (75% LTV) vs Bank Rate" ids={["mortgage_2y_75", "mortgage_5y_75", "bank_rate"]}
            names={["2-year fixed", "5-year fixed", "Bank Rate"]} unit="%" decimals={2} defaultFrom="2015" />
        </div>
        <div className="space-y-2">
          {data && <MarketMonitor rows={data.markets} />}
          <Panel title="Coverage & licensing">
            <ul className="list-disc space-y-1 pl-4 text-[11px] text-muted-foreground">
              <li><b className="text-foreground">Not real-time.</b> BoE daily series are published the following business day; ECB reference rates around 16:00 CET on TARGET working days.</li>
              <li><b className="text-foreground">Equity indices are not shown.</b> FTSE index data is proprietary and no free source with verified redistribution terms was found. Unofficial scraping is not used.</li>
              <li>BoE spot exchange rates (XUDL*) may contain LSEG/Bloomberg content with redistribution restrictions, so they are disabled by default; sterling crosses are derived from ECB reference rates and labelled as modifications.</li>
              <li>Gilt yields are model estimates from the BoE yield curve, not traded quotes.</li>
            </ul>
          </Panel>
        </div>
      </div>
    </div>
  );
}
