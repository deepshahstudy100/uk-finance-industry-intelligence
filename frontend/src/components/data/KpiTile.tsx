"use client";
import Link from "next/link";
import type { SeriesSummary } from "@/lib/api";
import { fmtChange, fmtValue, FREQ_LABEL } from "@/lib/format";
import { useInvestigate } from "@/lib/hooks";
import { cn } from "@/lib/utils";
import { Sparkline } from "@/components/charts/Sparkline";
import { DemoBadge, StatusBadge } from "./Status";

/** KPI tile: value + unit + period + change vs previous + status. The whole tile drills into the workspace. */
export function KpiTile({ s }: { s: SeriesSummary }) {
  const inv = useInvestigate();
  const demo = s.data_status === "demo";
  const ch = s.change;
  const up = ch?.value != null && ch.value > 0;
  const down = ch?.value != null && ch.value < 0;
  return (
    <Link
      href={inv({ series: s.id, period: s.latest?.period })}
      className={cn("group flex min-w-0 flex-col gap-1 rounded-md border bg-card p-2.5 hover:border-primary/50 hover:bg-accent/40 focus-visible:ring-2 focus-visible:ring-ring outline-none",
        demo && "border-demo/40 demo-hatch")}
    >
      <div className="flex items-start justify-between gap-2">
        <span className="line-clamp-2 text-[11px] leading-tight text-muted-foreground group-hover:text-foreground">{s.title}</span>
        <StatusBadge status={s.status} reasons={s.status_reasons} compact />
      </div>
      <div className="flex items-end justify-between gap-2">
        <div className="min-w-0">
          <div className="truncate text-xl font-semibold leading-none text-foreground tabular">
            {s.latest ? fmtValue(s.latest.value, s.unit, s.decimals) : "–"}
          </div>
          <div className="mt-1 text-[10px] text-muted-foreground tabular">
            {s.latest?.period ?? "no data"} · {FREQ_LABEL[s.frequency]}
          </div>
        </div>
        {s.spark && <span className="hidden shrink-0 sm:block"><Sparkline values={s.spark} color={demo ? "#c77dff" : "#3fb6d3"} /></span>}
      </div>
      <div className="flex items-center justify-between text-[10px] tabular">
        {ch ? (
          <span className={cn(up && "text-cyan", down && "text-serious", !up && !down && "text-muted-foreground")}>
            {fmtChange(ch.value, ch.unit)} <span className="text-muted-foreground">vs {ch.vs_period}</span>
          </span>
        ) : <span />}
        {demo && <DemoBadge />}
      </div>
    </Link>
  );
}
