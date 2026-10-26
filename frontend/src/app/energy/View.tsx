"use client";
import { EnergyNowPanel } from "@/components/data/MiscPanels";
import { Panel } from "@/components/data/Panel";
import { SeriesPanel } from "@/components/data/SeriesPanel";
import { PageHeader } from "@/components/shell/PageHeader";

export function View() {
  return (
    <div className="pb-6">
      <PageHeader title="Energy"
        description="GB electricity generation mix and carbon intensity (NESO, half-hourly), weekly UK road fuel prices (DESNZ), household energy prices within CPI, and output of the energy supply industry (SIC D)." />
      <div className="grid grid-cols-1 gap-2 px-3 xl:grid-cols-2">
        <EnergyNowPanel height={260} className="xl:col-span-2" />
        <SeriesPanel title="Road fuel pump prices (weekly)" ids={["fuel_petrol", "fuel_diesel"]} names={["Unleaded petrol", "Diesel"]}
          unit="pence per litre" decimals={1} defaultFrom="2018" subtitle="DESNZ weekly road fuel prices, UK average incl. duty and VAT" />
        <SeriesPanel title="CPI: housing, water, electricity, gas & fuels vs transport" ids={["cpi_div_04", "cpi_div_07", "cpi_yoy"]}
          names={["Housing & household energy (04)", "Transport (07)", "All-items CPI"]} unit="%" defaultFrom="2018"
          subtitle="ONS MM23 12-month rates (published COICOP divisions)" />
        <SeriesPanel title="Output: electricity, gas, steam & air conditioning (SIC D)" ids={["gva_D"]} unit="index" defaultFrom="2018" />
        <Panel title="Coverage notes">
          <ul className="list-disc space-y-1 pl-4 text-[11px] text-muted-foreground">
            <li>Generation mix and carbon intensity are modelled half-hourly estimates for Great Britain (Northern Ireland is a separate system). Where NESO has not yet published an &ldquo;actual&rdquo; intensity, the forecast is shown and labelled.</li>
            <li>DESNZ Energy Trends and quarterly energy prices are published as spreadsheets with changing layouts and are not yet parsed; no values from them are shown.</li>
            <li>Fuel CSV location is discovered each run via the GOV.UK Content API (the attachment URL changes with each release).</li>
          </ul>
        </Panel>
      </div>
    </div>
  );
}
