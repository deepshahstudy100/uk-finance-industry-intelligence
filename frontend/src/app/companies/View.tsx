"use client";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { ExternalLink } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useMeta } from "@/lib/hooks";
import { DataTable } from "@/components/data/DataTable";
import { Panel } from "@/components/data/Panel";
import { PageHeader } from "@/components/shell/PageHeader";

interface SearchResp { request_url: string; total_results: number; retrieved_at: string;
  items: { company_number: string; title: string; company_status: string; company_type: string; date_of_creation: string; address_snippet: string }[] }
interface ProfileResp {
  profile: Record<string, unknown> & { company_name?: string; sic_codes?: string[] };
  filings: { date: string; category: string; type: string; description: string; transaction_id: string }[];
  request_urls: string[]; web_url: string; retrieved_at: string; sic_sections: { sic: string; section: string | null }[]; attribution: string;
}

export function View() {
  const { data: meta } = useMeta();
  const [q, setQ] = useState("");
  const [term, setTerm] = useState("");
  const [num, setNum] = useState<string | null>(null);
  const search = useQuery({ queryKey: ["ch", term], queryFn: () => api<SearchResp>(`/companies/search?q=${encodeURIComponent(term)}`), enabled: term.length > 1 && !!meta?.companies_house_enabled, retry: false });
  const prof = useQuery({ queryKey: ["chp", num], queryFn: () => api<ProfileResp>(`/companies/${num}`), enabled: !!num, retry: false });
  const err = (search.error || prof.error) as ApiError | null;
  return (
    <div className="pb-6">
      <PageHeader title="Companies"
        description="Company profiles and filing history from the Companies House Public Data API (free key, 600 requests / 5 min). Officer personal data is deliberately not displayed." />
      {meta && !meta.companies_house_enabled && (
        <div className="mx-3 mb-2 rounded border border-warning/40 bg-warning/5 p-3 text-[11px]">
          <b className="text-warning">Companies House is not configured.</b> The API requires a free key. Register at{" "}
          <a className="text-cyan hover:underline" href="https://developer.company-information.service.gov.uk/" target="_blank" rel="noreferrer">developer.company-information.service.gov.uk</a>,
          create a REST key and set <code>UKINTEL_COMPANIES_HOUSE_API_KEY</code> in the backend environment. All other modules work without it.
        </div>
      )}
      <div className="grid grid-cols-1 gap-2 px-3 xl:grid-cols-2">
        <Panel title="Search the register" subtitle={search.data ? `${search.data.total_results} results · retrieved ${search.data.retrieved_at}` : "Name or number"}
          loading={search.isLoading && search.fetchStatus !== "idle"} error={err?.message}
          actions={<form onSubmit={(e) => { e.preventDefault(); setTerm(q.trim()); }} className="flex gap-1">
            <input value={q} onChange={(e) => setQ(e.target.value)} disabled={!meta?.companies_house_enabled} placeholder="e.g. Rolls-Royce"
              aria-label="Company search" className="h-7 w-56 rounded border bg-secondary px-1.5 text-[11px] outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50" />
            <button disabled={!meta?.companies_house_enabled} className="h-7 rounded border border-primary/50 px-2 text-[11px] text-primary disabled:opacity-40">Search</button>
          </form>}>
          <DataTable rows={search.data?.items ?? []} rowKey={(r) => r.company_number} selectedKey={num} onRowClick={(r) => setNum(r.company_number)} maxHeight={460}
            columns={[
              { key: "t", header: "Name", value: (r) => r.title },
              { key: "n", header: "Number", value: (r) => r.company_number },
              { key: "s", header: "Status", value: (r) => r.company_status },
              { key: "c", header: "Incorporated", value: (r) => r.date_of_creation },
              { key: "a", header: "Registered address", value: (r) => r.address_snippet },
            ]} />
        </Panel>
        <Panel title={prof.data?.profile.company_name ? String(prof.data.profile.company_name) : "Company profile"}
          subtitle={prof.data ? `Retrieved ${prof.data.retrieved_at} · ${prof.data.attribution}` : "Select a company"} loading={prof.isLoading}
          actions={prof.data ? <a href={prof.data.web_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-[11px] text-cyan">Register entry <ExternalLink className="size-3" /></a> : undefined}>
          {prof.data && (
            <div className="space-y-2">
              <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-[11px]">
                {Object.entries(prof.data.profile).filter(([k]) => !["registered_office_address", "accounts", "confirmation_statement", "sic_codes"].includes(k)).map(([k, v]) => (
                  <div key={k} className="contents"><dt className="text-muted-foreground">{k.replaceAll("_", " ")}</dt><dd>{String(v)}</dd></div>
                ))}
              </dl>
              <div className="text-[11px]"><span className="text-muted-foreground">SIC 2007 codes: </span>
                {prof.data.sic_sections.map((s) => (
                  <Link key={s.sic} href={s.section ? `/industry?sector=${s.section}` : "#"} className="mr-2 rounded border px-1 hover:border-primary/50">{s.sic} → section {s.section ?? "?"}</Link>
                ))}
              </div>
              <DataTable rows={prof.data.filings} rowKey={(r) => r.transaction_id} maxHeight={280}
                columns={[
                  { key: "d", header: "Date", value: (r) => r.date },
                  { key: "c", header: "Category", value: (r) => r.category },
                  { key: "t", header: "Type", value: (r) => r.type },
                  { key: "x", header: "Description code", value: (r) => r.description },
                ]} />
              <p className="text-[10px] text-muted-foreground">API requests: {prof.data.request_urls.join(" · ")}</p>
            </div>
          )}
        </Panel>
      </div>
    </div>
  );
}
