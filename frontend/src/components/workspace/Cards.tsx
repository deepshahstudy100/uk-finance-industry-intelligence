"use client";
import Link from "next/link";
import { ExternalLink } from "lucide-react";
import type { Analysis, AnalysisPoint, SeriesDetail } from "@/lib/api";
import { fmtChange, fmtDate, fmtDateTime, fmtValue, FREQ_LABEL, LATENCY_LABEL } from "@/lib/format";
import { Panel } from "@/components/data/Panel";

function Row({ k, children }: { k: string; children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[112px_minmax(0,1fr)] gap-2 border-b border-border/50 py-1 text-[11px] last:border-0">
      <dt className="text-muted-foreground">{k}</dt>
      <dd className="min-w-0 break-words text-foreground">{children}</dd>
    </div>
  );
}

function Ext({ href, children }: { href: string | null | undefined; children?: React.ReactNode }) {
  if (!href) return <span className="text-muted-foreground">–</span>;
  return (
    <a href={href} target="_blank" rel="noreferrer" className="inline-flex max-w-full items-center gap-1 text-cyan hover:underline">
      <span className="truncate">{children ?? href}</span><ExternalLink className="size-3 shrink-0" />
    </a>
  );
}

const SA: Record<string, string> = { SA: "Seasonally adjusted", NSA: "Not seasonally adjusted", "n/a": "Not applicable" };
const MT: Record<string, string> = {
  level: "Level (amount/count)", index: "Index number", price: "Price", rate: "Rate (%)",
  growth_rate: "Growth rate (% change)", share: "Share / ratio",
};

export function SelectedObservation({ d, a, point, geoName, dimLabel }: {
  d: SeriesDetail; a?: Analysis; point: AnalysisPoint | null; geoName?: string | null; dimLabel?: string;
}) {
  const idn = d.identity;
  const flags = (point?.flags ?? {}) as Record<string, unknown>;
  return (
    <Panel title="Selected observation" subtitle="Click a chart point or table row to change" demo={a?.data_status === "demo"}>
      {!point ? <p className="text-[11px] text-muted-foreground">No observation selected.</p> : (
        <>
          <div className="mb-2 flex items-baseline justify-between gap-2">
            <div className="text-2xl font-semibold tabular">{fmtValue(point.value, idn.unit, idn.decimals, false)}</div>
            <div className="text-right text-[11px] text-muted-foreground">{point.period}<br />{FREQ_LABEL[idn.frequency]}</div>
          </div>
          <dl>
            <Row k="Geography">{geoName ?? "–"}</Row>
            {dimLabel && <Row k="Breakdown">{dimLabel}</Row>}
            <Row k="Status"><span className={point.status === "provisional" || point.status === "forecast" ? "text-warning" : ""}>{point.status}</span></Row>
            <Row k="Period-on-period">{fmtChange(point.pop, a?.change_unit ?? "%")}</Row>
            <Row k="Year-on-year">{d.rules.year_on_year?.allowed ? fmtChange(point.yoy, a?.change_unit ?? "%") : <span className="text-muted-foreground">n/a</span>}</Row>
            <Row k="Rolling mean">{fmtValue(point.rolling, idn.unit, idn.decimals, false)} ({a?.window} obs)</Row>
            {"ci95_pp" in flags && <Row k="95% conf. int.">±{String(flags.ci95_pp)}pp (published by source)</Row>}
            {"cv_pct" in flags && <Row k="Coeff. of variation">{String(flags.cv_pct)}% {flags.reliability ? `· ${String(flags.reliability)}` : ""}</Row>}
            {"forecast" in flags && <Row k="NESO values">actual {String(flags.actual ?? "–")} · forecast {String(flags.forecast ?? "–")} · {String(flags.index ?? "")}</Row>}
            {"derived" in flags && <Row k="Derived">{String(flags.formula)}</Row>}
            {"duty_ppl" in flags && <Row k="Duty">{String(flags.duty_ppl)}p/litre</Row>}
            {"obs_status" in flags && <Row k="Source flag">{String(flags.obs_status)}</Row>}
          </dl>
        </>
      )}
    </Panel>
  );
}

export function IdentityCard({ d }: { d: SeriesDetail }) {
  const i = d.identity;
  return (
    <Panel title="Identity & definition">
      <p className="mb-2 text-[11px] leading-relaxed text-foreground">{i.definition}</p>
      <dl>
        <Row k="Metric ID"><code className="text-[10px]">{i.id}</code></Row>
        <Row k="Unit">{i.unit}{d.provenance.source_unit && d.provenance.source_unit !== i.unit ? ` (source: ${d.provenance.source_unit})` : ""}</Row>
        <Row k="Measure type">{MT[i.measure_type] ?? i.measure_type}</Row>
        <Row k="Frequency">{FREQ_LABEL[i.frequency]}</Row>
        <Row k="Adjustment">{SA[i.seasonal_adjustment]}</Row>
        {i.price_basis && <Row k="Price basis">{i.price_basis === "CVM" ? "Chained volume measure (real terms)" : "Current prices (nominal)"}</Row>}
        {i.base_period && <Row k="Base period">{i.base_period}</Row>}
        <Row k="Geography">{i.geography === "uk" ? "United Kingdom" : i.geography === "gb" ? "Great Britain" : "UK, nations, ITL1 regions" + (i.geography.includes("lad") ? ", local authorities" : "")}</Row>
        {i.industry_classification && <Row k="Industry">{i.industry ? `${i.industry}: ${i.industry_name}` : "By section"} · {i.industry_classification}</Row>}
        {i.dim_kind && <Row k="Breakdown">{i.dim_kind.replace("_", " ")}</Row>}
      </dl>
    </Panel>
  );
}

export function ProvenanceCard({ d }: { d: SeriesDetail }) {
  const p = d.provenance;
  return (
    <Panel title="Provenance" subtitle={LATENCY_LABEL[p.latency_class]}>
      <dl>
        <Row k="Publisher">{p.publisher}</Row>
        <Row k="Source">{p.source_name}</Row>
        <Row k="Dataset / ID"><code className="text-[10px]">{p.dataset_identifier}</code>{p.source_title ? <div className="text-[10px] text-muted-foreground">{p.source_title}</div> : null}</Row>
        <Row k="Source page"><Ext href={p.source_page_url}>Open publisher page</Ext></Row>
        {p.dataset_url && <Row k="Dataset"><Ext href={p.dataset_url}>Dataset / definition</Ext></Row>}
        <Row k="API request"><Ext href={p.request_url}>{p.request_url ? shorten(p.request_url) : undefined}</Ext></Row>
        {p.bulletins.length > 0 && <Row k="Bulletin">{p.bulletins.map((b) => <div key={b}><Ext href={b}>{shorten(b)}</Ext></div>)}</Row>}
        <Row k="Published">{fmtDateTime(p.release_date)}</Row>
        <Row k="Next release">{p.next_release ?? "Not announced via API"}</Row>
        <Row k="Retrieved">{fmtDateTime(p.last_retrieved_at)}</Row>
        <Row k="Ingestion run">{p.last_run_id ? <Link href={`/sources?run=${p.last_run_id}#${p.source_id}`} className="text-cyan hover:underline">#{p.last_run_id} (request log)</Link> : "–"}</Row>
        <Row k="Update cycle">{p.update_frequency}</Row>
        {p.formula && <Row k="Transformation">Derived: <code className="text-[10px]">{p.formula}</code>{p.modification_notice ? <div className="text-[10px] text-muted-foreground">{p.modification_notice}</div> : null}</Row>}
        <Row k="Licence"><Ext href={p.licence_url}>{p.licence}</Ext></Row>
        <Row k="Attribution"><span className="text-[10px]">{p.attribution}</span></Row>
        {d.version_count ? <Row k="Published versions">{d.version_count} (ONS version history; see Revisions)</Row> : null}
      </dl>
    </Panel>
  );
}

function shorten(u: string) {
  try {
    const x = new URL(u);
    const s = x.host + x.pathname + (x.search ? "?…" : "");
    return s.length > 60 ? s.slice(0, 58) + "…" : s;
  } catch {
    return u;
  }
}

export { fmtDate };
