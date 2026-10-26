"use client";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { Gauge } from "lucide-react";
import { api, qs } from "@/lib/api";
import { fmtDateTime, fmtNumber, fmtSigned } from "@/lib/format";
import { cn } from "@/lib/utils";

export interface ScoreResp {
  available: boolean; reason?: string; period: string; score: number; z: number; band: string;
  change_vs_previous: number | null; previous_period: string | null; change_vs_year_ago: number | null;
  weights: Record<string, number>;
  pillars: { id: string; label: string; weight: number; available: boolean; z: number | null; score: number | null }[];
  components: { id: string; pillar: string; title: string; inputs: string[]; transform?: string; direction?: string; unit?: string;
    available: boolean; reason?: string; value?: number | null; period_used?: string | null; carried_forward?: boolean;
    z?: number | null; contribution_z?: number | null; mean?: number; std?: number; n?: number }[];
  history: { period: string; score: number; z: number; pillars: Record<string, number | null> }[];
  method: Record<string, string | number>; caveats: string[]; missing_components: string[];
  computed_at: string; latest_input_release: string | null; label: string; data_status: "real";
  inputs: Record<string, { title: string; last_period: string; release_date: string | null; next_release: string | null;
    retrieved_at: string | null; publisher: string }>;
}

export function useScore(weights?: string | null) {
  return useQuery({
    queryKey: ["score", weights ?? null],
    queryFn: () => api<ScoreResp>(`/score${qs({ weights })}`),
    refetchInterval: 60_000, // "live": recomputed server-side from the latest retrieved data
    placeholderData: keepPreviousData, // keep controls mounted while a re-weighted score is computed
  });
}

/** 0-100 track with neutral midpoint at 50 (historical average). */
export function ScoreTrack({ score }: { score: number }) {
  return (
    <div className="relative h-2 w-full rounded-full" aria-hidden
      style={{ background: "linear-gradient(90deg,#e66767 0%,#383835 50%,#3987e5 100%)" }}>
      <div className="absolute top-1/2 h-4 w-1 -translate-x-1/2 -translate-y-1/2 rounded bg-foreground shadow" style={{ left: `${Math.min(100, Math.max(0, score))}%` }} />
      <div className="absolute top-full mt-0.5 flex w-full justify-between text-[9px] text-muted-foreground"><span>0</span><span>50 = avg</span><span>100</span></div>
    </div>
  );
}

export function LivePulse({ at }: { at?: string }) {
  return (
    <span className="inline-flex items-center gap-1 text-[10px] text-muted-foreground" title="Recomputed every minute from the latest retrieved data">
      <span className="relative flex size-2"><span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-good opacity-60" /><span className="relative inline-flex size-2 rounded-full bg-good" /></span>
      live · {at ? fmtDateTime(at) : "…"}
    </span>
  );
}

/** Compact tile for the command centre. */
export function ScoreTile({ className }: { className?: string }) {
  const { data, isLoading } = useScore();
  return (
    <Link href="/score" className={cn("flex min-w-0 flex-col gap-1.5 rounded-md border border-primary/40 bg-card p-2.5 hover:bg-accent/40 outline-none focus-visible:ring-2 focus-visible:ring-ring", className)}>
      <div className="flex items-center justify-between gap-2">
        <span className="inline-flex items-center gap-1 text-[11px] text-muted-foreground"><Gauge className="size-3.5 text-primary" /> Economic Conditions Score</span>
        <LivePulse at={data?.computed_at} />
      </div>
      {isLoading ? <span className="text-xs text-muted-foreground">Computing…</span> : data?.available ? (
        <>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-semibold tabular">{fmtNumber(data.score, 0)}</span>
            <span className="text-[11px] text-muted-foreground">/100 · {data.period}</span>
            <span className={cn("ml-auto text-[10px] tabular", (data.change_vs_previous ?? 0) >= 0 ? "text-cyan" : "text-serious")}>
              {fmtSigned(data.change_vs_previous)} pts vs {data.previous_period}</span>
          </div>
          <ScoreTrack score={data.score} />
          <div className="mt-2 text-[10px] text-muted-foreground">{data.band} · platform construction, not an official statistic</div>
        </>
      ) : <span className="text-xs text-muted-foreground">{data?.reason ?? "Unavailable"}</span>}
    </Link>
  );
}
