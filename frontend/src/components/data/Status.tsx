"use client";
import { AlertTriangle, CheckCircle2, CircleDashed, Clock, FlaskConical, Hourglass, MinusCircle, XCircle } from "lucide-react";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { STATUS_COLOR } from "@/lib/colors";
import { cn } from "@/lib/utils";

const LABEL: Record<string, string> = {
  current: "Current", provisional: "Provisional", delayed: "Delayed", degraded: "Degraded", stale: "Stale",
  unavailable: "Unavailable", demo: "Demo data", disabled: "Disabled", on_demand: "On demand",
  not_configured: "Not configured",
};
const ICON: Record<string, typeof CheckCircle2> = {
  current: CheckCircle2, provisional: Hourglass, delayed: Clock, degraded: AlertTriangle, stale: AlertTriangle,
  unavailable: XCircle, demo: FlaskConical, disabled: MinusCircle, on_demand: CircleDashed,
  not_configured: MinusCircle,
};

/** Source/series status: icon + label + colour (never colour alone). Reasons on hover. */
export function StatusBadge({ status, reasons, compact = false, className }: {
  status: string; reasons?: string[]; compact?: boolean; className?: string;
}) {
  const Icon = ICON[status] ?? CircleDashed;
  const color = STATUS_COLOR[status] ?? "#8a96a8";
  const badge = (
    <span
      className={cn("inline-flex items-center gap-1 rounded-sm border px-1.5 py-px text-[10px] font-medium uppercase tracking-wide whitespace-nowrap",
        className)}
      style={{ color, borderColor: `${color}55`, background: `${color}14` }}
    >
      <Icon className="size-3" aria-hidden />
      {!compact && LABEL[status]}
      {compact && <span className="sr-only">{LABEL[status]}</span>}
    </span>
  );
  if (!reasons?.length) return badge;
  return (
    <Tooltip>
      <TooltipTrigger render={<span className="inline-flex" tabIndex={0} />}>{badge}</TooltipTrigger>
      <TooltipContent className="max-w-xs text-xs">
        <div className="font-semibold mb-1">{LABEL[status] ?? status}</div>
        <ul className="list-disc pl-4 space-y-0.5">{reasons.map((r, i) => <li key={i}>{r}</li>)}</ul>
      </TooltipContent>
    </Tooltip>
  );
}

/** Shown wherever synthetic sample data is displayed. */
export function DemoBadge({ className }: { className?: string }) {
  return (
    <Tooltip>
      <TooltipTrigger render={<span className="inline-flex" tabIndex={0} />}>
        <span className={cn("inline-flex items-center gap-1 rounded-sm border border-demo/50 bg-demo/10 px-1.5 py-px text-[10px] font-bold uppercase tracking-wider text-demo demo-hatch", className)}>
          <FlaskConical className="size-3" aria-hidden /> Demo · sample data
        </span>
      </TooltipTrigger>
      <TooltipContent className="max-w-xs text-xs">
        Synthetic values generated because no real observations have been retrieved for this series. Not real
        statistics; never mixed with real data.
      </TooltipContent>
    </Tooltip>
  );
}

export function DataStatusBadge({ status }: { status: "real" | "demo" | null | undefined }) {
  return status === "demo" ? <DemoBadge /> : null;
}
