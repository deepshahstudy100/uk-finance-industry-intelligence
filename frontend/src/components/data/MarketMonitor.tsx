"use client";
import Link from "next/link";
import type { SeriesSummary } from "@/lib/api";
import { fmtChange, fmtValue } from "@/lib/format";
import { useInvestigate } from "@/lib/hooks";
import { cn } from "@/lib/utils";
import { Sparkline } from "@/components/charts/Sparkline";
import { Panel } from "./Panel";
import { StatusBadge } from "./Status";

const TIMING: Record<string, string> = {
  boe: "End of day · published next business day",
  ecb: "ECB reference rate · ~16:00 CET",
};

/** Rates and FX with explicit timing class. Nothing here is a real-time price. */
export function MarketMonitor({ rows, className }: { rows: SeriesSummary[]; className?: string }) {
  const inv = useInvestigate();
  return (
    <Panel title="Market monitor" className={className}
      subtitle="Bank of England (OGL) and ECB reference rates. Delayed/end-of-day data, not real-time quotes.">
      <table className="w-full text-[11px]">
        <thead className="text-muted-foreground">
          <tr className="border-b">
            <th className="py-1 text-left font-medium">Instrument</th>
            <th className="py-1 text-right font-medium">Last</th>
            <th className="py-1 text-right font-medium">Chg</th>
            <th className="py-1 text-right font-medium">As of</th>
            <th className="py-1 pl-2 text-left font-medium">Trend</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => {
            const up = (r.change?.value ?? 0) > 0;
            const dn = (r.change?.value ?? 0) < 0;
            return (
              <tr key={r.id} className="border-b border-border/50 hover:bg-accent/40">
                <td className="py-1 pr-2">
                  <Link href={inv({ series: r.id, period: r.latest?.period })} className="hover:text-primary">{r.title}</Link>
                  <div className="text-[9px] text-muted-foreground">{TIMING[r.source_id] ?? r.source_id}</div>
                </td>
                <td className="py-1 text-right tabular">{fmtValue(r.latest?.value, r.unit, r.decimals > 3 ? 3 : r.decimals)}</td>
                <td className={cn("py-1 text-right tabular", up && "text-cyan", dn && "text-serious")}>
                  {fmtChange(r.change?.value, r.change?.unit ?? "%", r.change?.unit === "pp" ? 3 : 2)}
                </td>
                <td className="py-1 text-right tabular text-muted-foreground">
                  <span className="mr-1">{r.latest?.period ?? "–"}</span>
                  <StatusBadge status={r.status} reasons={r.status_reasons} compact />
                </td>
                <td className="py-1 pl-2"><Sparkline values={r.spark ?? []} width={70} height={18}
                  color={r.data_status === "demo" ? "#c77dff" : "#3fb6d3"} /></td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <p className="mt-1.5 text-[9px] text-muted-foreground">
        Equity indices are not shown: no free source with verified redistribution terms. GBP crosses are derived from ECB
        reference rates (stated as a modification per ECB terms).
      </p>
    </Panel>
  );
}
