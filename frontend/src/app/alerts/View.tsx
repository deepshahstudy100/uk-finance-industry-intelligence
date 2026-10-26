"use client";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api, type AlertItem } from "@/lib/api";
import { AlertsPanel } from "@/components/data/MiscPanels";
import { Seg } from "@/components/data/Panel";
import { PageHeader } from "@/components/shell/PageHeader";

const KINDS = ["all", "outlier", "revision", "stale", "delayed", "source_failure", "validation"] as const;

export function View() {
  const [kind, setKind] = useState<(typeof KINDS)[number]>("all");
  const [active, setActive] = useState<"active" | "all">("active");
  const { data } = useQuery({
    queryKey: ["alerts", kind, active],
    queryFn: () => api<AlertItem[]>(`/alerts?limit=300&active=${active === "active"}${kind !== "all" ? `&kind=${kind}` : ""}`),
    refetchInterval: 60_000,
  });
  return (
    <div className="pb-6">
      <PageHeader title="Anomaly & data alerts"
        description="Outliers are robust statistical flags on period-on-period changes (median/MAD z ≥ 3.5) - prompts to check releases, not conclusions. Revisions, stale/delayed data and source failures are raised automatically and resolve when the condition clears.">
        <Seg value={active} onChange={setActive} label="State" options={[{ value: "active", label: "Active" }, { value: "all", label: "Include resolved" }]} />
        <Seg value={kind} onChange={setKind} label="Kind" options={KINDS.map((k) => ({ value: k, label: k.replace("_", " ") }))} />
      </PageHeader>
      <div className="px-3"><AlertsPanel alerts={data ?? []} title={`${data?.length ?? 0} alerts`} /></div>
    </div>
  );
}
