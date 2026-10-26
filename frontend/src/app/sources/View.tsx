"use client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "next/navigation";
import { useState } from "react";
import { ExternalLink, RefreshCw } from "lucide-react";
import { api, type Meta, type RunInfo, type SourceRow } from "@/lib/api";
import { ago, fmtDateTime, fmtNumber, LATENCY_LABEL } from "@/lib/format";
import { useMeta } from "@/lib/hooks";
import { Panel } from "@/components/data/Panel";
import { StatusBadge } from "@/components/data/Status";
import { PageHeader } from "@/components/shell/PageHeader";
import { cn } from "@/lib/utils";

export function View() {
  const sp = useSearchParams();
  const runParam = sp.get("run");
  const { data, isLoading } = useQuery({ queryKey: ["sources"], queryFn: () => api<SourceRow[]>("/sources"), refetchInterval: 30_000 });
  const { data: meta } = useMeta();
  const [open, setOpen] = useState<string | null>(null);
  return (
    <div className="pb-6">
      <PageHeader title="Source registry & health"
        description="Every integrated source with its licence, authentication, documented or self-imposed rate limit, schedule, verification record and live status. Status is judged against each source's own publication schedule." />
      {runParam && <div className="px-3 pb-2"><RunDetail id={Number(runParam)} /></div>}
      <div className="space-y-2 px-3">
        {isLoading && <p className="text-xs text-muted-foreground">Loading…</p>}
        {data?.map((s) => (
          <section key={s.id} id={s.id} className="rounded-md border bg-card">
            <div className="flex flex-wrap items-center gap-2 border-b bg-panel-header/60 px-3 py-1.5">
              <StatusBadge status={s.status} reasons={s.status_reasons} />
              <h2 className="text-[12px] font-semibold">{s.publisher}</h2>
              <span className="text-[11px] text-muted-foreground">{s.name}</span>
              <span className="ml-auto text-[10px] text-muted-foreground">{LATENCY_LABEL[s.latency_class]}</span>
              <RefreshButton id={s.id} disabled={s.latency_class === "on_demand"} />
              <button onClick={() => setOpen(open === s.id ? null : s.id)} className="rounded border px-2 py-0.5 text-[11px] hover:bg-accent">{open === s.id ? "Hide runs" : "Run log"}</button>
            </div>
            <div className="grid grid-cols-1 gap-x-6 gap-y-1 p-3 text-[11px] md:grid-cols-2 xl:grid-cols-4">
              <KV k="Licence"><a href={s.licence_url} target="_blank" rel="noreferrer" className="text-cyan hover:underline">{s.licence}</a></KV>
              <KV k="Authentication">{s.auth === "none" ? "None required" : s.auth === "optional_free_key" ? "Optional free key" : "Free key required"}</KV>
              <KV k="Rate limit">{s.rate_limit.note} {s.rate_limit.documented ? "(documented)" : "(self-imposed)"}</KV>
              <KV k="Update frequency">{s.update_frequency}</KV>
              <KV k="Poll interval">{s.refresh_minutes ? `every ${s.refresh_minutes >= 1440 ? `${s.refresh_minutes / 1440} d` : `${s.refresh_minutes} min`}` : "on demand"} · stale after {s.stale_after_hours} h</KV>
              <KV k="Last success">{fmtDateTime(s.last_success_at)} ({ago(s.last_success_at)})</KV>
              <KV k="Last attempt">{fmtDateTime(s.last_attempt_at)} · {s.consecutive_failures} consecutive failure(s)</KV>
              <KV k="Observations stored">{fmtNumber(s.observations, 0)} across {s.series.length} series</KV>
              <KV k="Endpoint"><code className="break-all text-[10px]">{s.api_base}</code></KV>
              <KV k="Documentation"><a href={s.docs_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-cyan hover:underline">docs <ExternalLink className="size-3" /></a></KV>
              <KV k="Attribution"><span className="text-[10px]">{s.attribution}</span></KV>
              {s.last_error && <KV k="Last error"><span className="text-critical">{s.last_error}</span></KV>}
              <div className="md:col-span-2 xl:col-span-4"><KV k="Verification">{s.verification}</KV></div>
              {s.caveats.length > 0 && <div className="md:col-span-2 xl:col-span-4"><KV k="Caveats"><ul className="list-disc pl-4">{s.caveats.map((c) => <li key={c}>{c}</li>)}</ul></KV></div>}
            </div>
            {open === s.id && <Runs id={s.id} />}
          </section>
        ))}
        {meta && <CostPanel meta={meta} />}
      </div>
    </div>
  );
}

function KV({ k, children }: { k: string; children: React.ReactNode }) {
  return <div className="min-w-0"><div className="text-[9px] uppercase tracking-wider text-muted-foreground">{k}</div><div className="min-w-0 break-words">{children}</div></div>;
}

function RefreshButton({ id, disabled }: { id: string; disabled?: boolean }) {
  const qc = useQueryClient();
  const m = useMutation({
    mutationFn: () => api<{ queued: boolean; reason?: string }>(`/sources/${id}/refresh`, { method: "POST" }),
    onSuccess: () => setTimeout(() => qc.invalidateQueries(), 3000),
  });
  return (
    <button disabled={disabled || m.isPending} onClick={() => m.mutate()} title="Run ingestion now (respects rate limits)"
      className="inline-flex items-center gap-1 rounded border px-2 py-0.5 text-[11px] hover:bg-accent disabled:opacity-40">
      <RefreshCw className={cn("size-3", m.isPending && "animate-spin")} /> {m.data ? (m.data.queued ? "Queued" : m.data.reason) : m.error ? "Refused" : "Refresh"}
    </button>
  );
}

function Runs({ id }: { id: string }) {
  const { data } = useQuery({ queryKey: ["runs", id], queryFn: () => api<RunInfo[]>(`/sources/${id}/runs?limit=15`) });
  return (
    <div className="border-t p-3">
      <table className="w-full text-[11px]">
        <thead className="text-muted-foreground"><tr><th className="text-left">Run</th><th className="text-left">Started</th><th className="text-left">Job</th><th className="text-left">Status</th>
          <th className="text-right">Fetched</th><th className="text-right">New</th><th className="text-right">Revised</th><th className="text-right">Requests</th><th className="pl-2 text-left">Message</th></tr></thead>
        <tbody>{data?.map((r) => (
          <tr key={r.id} className="border-t border-border/50">
            <td><a href={`/sources?run=${r.id}#${id}`} className="text-cyan hover:underline">#{r.id}</a></td><td>{fmtDateTime(r.started_at)}</td><td>{r.job}</td>
            <td className={r.status === "failed" ? "text-critical" : r.status === "partial" ? "text-warning" : "text-good"}>{r.status}</td>
            <td className="text-right tabular">{r.fetched}</td><td className="text-right tabular">{r.inserted}</td><td className="text-right tabular">{r.revised}</td>
            <td className="text-right tabular">{r.request_count}</td><td className="pl-2 text-muted-foreground">{r.message}</td>
          </tr>))}
        </tbody>
      </table>
    </div>
  );
}

function RunDetail({ id }: { id: number }) {
  const { data, error } = useQuery({ queryKey: ["run", id], queryFn: () => api<RunInfo>(`/runs/${id}`) });
  return (
    <Panel title={`Ingestion run #${id}${data ? ` · ${data.source_id} · ${data.status}` : ""}`} subtitle={data ? `${fmtDateTime(data.started_at)} → ${fmtDateTime(data.finished_at)} · fetched ${data.fetched}, new ${data.inserted}, revised ${data.revised}, unchanged ${data.unchanged}` : undefined}
      error={(error as Error | null)?.message}>
      {data?.errors?.length ? <ul className="mb-2 list-disc pl-4 text-[11px] text-critical">{data.errors.map((e, i) => <li key={i}>{e.series_id ?? "source"}: {e.kind} – {e.message}</li>)}</ul> : null}
      <div className="max-h-64 overflow-auto">
        <table className="w-full text-[10px]">
          <thead className="sticky top-0 bg-card text-muted-foreground"><tr><th className="text-left">Request URL</th><th>Status</th><th>Attempt</th><th className="text-right">ms</th><th className="text-right">bytes</th><th>Via</th></tr></thead>
          <tbody>{data?.requests?.map((q, i) => (
            <tr key={i} className="border-t border-border/50"><td className="max-w-[60ch] truncate"><a href={q.url} target="_blank" rel="noreferrer" className="text-cyan hover:underline">{q.url}</a></td>
              <td className="text-center">{q.status ?? "–"}</td><td className="text-center">{q.attempt}</td><td className="text-right tabular">{q.ms}</td><td className="text-right tabular">{q.bytes}</td><td className="text-center">{q.via}</td></tr>))}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

function CostPanel({ meta }: { meta: Meta }) {
  return (
    <Panel title="Cost & not-integrated sources" subtitle={meta.statement}>
      <p className="mb-2 text-[11px]">Paid dependencies required for core operation: <b>{meta.paid_dependencies.length ? meta.paid_dependencies.join(", ") : "none"}</b>. Demo mode: <b>{meta.demo_mode}</b>.</p>
      <ul className="space-y-1 text-[11px]">
        {meta.not_integrated.map((n) => <li key={n.name}><b>{n.name}</b> — <span className="text-muted-foreground">{n.reason}</span></li>)}
      </ul>
    </Panel>
  );
}
