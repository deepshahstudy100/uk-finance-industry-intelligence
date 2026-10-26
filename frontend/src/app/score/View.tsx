"use client";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useMemo, useState } from "react";
import { INK, seriesColor } from "@/lib/colors";
import { fmtDateTime, fmtNumber, fmtSigned, fmtValue } from "@/lib/format";
import { useInvestigate } from "@/lib/hooks";
import { EChart } from "@/components/charts/EChart";
import { baseText, gridBase, tooltipBase } from "@/components/charts/theme";
import { TimeSeriesChart } from "@/components/charts/TimeSeriesChart";
import { DataTable } from "@/components/data/DataTable";
import { LivePulse, ScoreTrack, useScore } from "@/components/data/EconomicScore";
import { Panel, Seg, Stat } from "@/components/data/Panel";
import { PageHeader } from "@/components/shell/PageHeader";
import { cn } from "@/lib/utils";

const PILLAR_ORDER = ["growth", "labour", "prices", "financial"];

export function View() {
  const sp = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const inv = useInvestigate();
  const wParam = sp.get("w");
  const { data, isLoading, error, dataUpdatedAt } = useScore(wParam);
  const [showPillars, setShowPillars] = useState<"score" | "pillars">("score");
  const weights = useMemo(() => {
    const w: Record<string, number> = { growth: 1, labour: 1, prices: 1, financial: 1 };
    for (const p of (wParam ?? "").split(",")) { const [k, v] = p.split(":"); if (k && v && !Number.isNaN(Number(v))) w[k] = Number(v); }
    return w;
  }, [wParam]);
  // Read the live URL at click time so rapid clicks accumulate (React state may not have re-rendered yet).
  const setWeight = (k: string, delta: number) => {
    const n = new URLSearchParams(window.location.search);
    const cur: Record<string, number> = { growth: 1, labour: 1, prices: 1, financial: 1 };
    for (const p of (n.get("w") ?? "").split(",")) { const [a, b] = p.split(":"); if (a && b && !Number.isNaN(Number(b))) cur[a] = Number(b); }
    cur[k] = Math.max(0, Math.min(5, cur[k] + delta));
    const str = PILLAR_ORDER.map((p) => `${p}:${cur[p]}`).join(",");
    if (str === "growth:1,labour:1,prices:1,financial:1") n.delete("w"); else n.set("w", str);
    const url = `${pathname}?${n.toString()}`;
    window.history.replaceState(null, "", url);
    router.replace(url, { scroll: false });
  };
  const from = sp.get("from");
  const hist = (data?.history ?? []).filter((h) => !from || h.period >= from.slice(0, 7));
  const series = showPillars === "score"
    ? [{ key: "score", name: "Economic Conditions Score", points: hist.map((h) => ({ t: `${h.period}-01`, v: h.score, period: h.period })) }]
    : PILLAR_ORDER.map((p, i) => ({ key: p, name: data?.pillars.find((x) => x.id === p)?.label ?? p, colorIndex: i,
      points: hist.map((h) => ({ t: `${h.period}-01`, v: h.pillars[p] ?? null, period: h.period })) }));
  const contribOpt = useMemo(() => {
    const comps = (data?.components ?? []).filter((c) => c.contribution_z != null);
    return {
      animation: false, grid: { ...gridBase, top: 4, bottom: 4 },
      tooltip: { ...tooltipBase, formatter: (p: { dataIndex: number }) => { const c = comps[p.dataIndex];
        return `<b>${c.title}</b><br/>z = ${fmtNumber(c.z, 2)} · contribution ${fmtNumber(c.contribution_z, 3)} (z units)<br/><span style="color:${INK.muted}">${c.direction}</span>`; } },
      xAxis: { type: "value", axisLabel: baseText, splitLine: { lineStyle: { color: INK.grid } } },
      yAxis: { type: "category", inverse: true, data: comps.map((c) => c.title), axisLabel: { ...baseText, color: INK.secondary, width: 210, overflow: "truncate" }, axisLine: { show: false }, axisTick: { show: false } },
      series: [{ type: "bar", barMaxWidth: 12, data: comps.map((c) => ({ value: c.contribution_z, itemStyle: { color: (c.contribution_z ?? 0) >= 0 ? seriesColor(0) : "#e66767", borderRadius: 2 } })) }],
    };
  }, [data]);

  return (
    <div className="pb-6">
      <PageHeader title="Economic Conditions Score"
        description="A transparent composite of eight published UK indicators across growth, labour market, price stability and financial conditions. Recomputed live from the latest retrieved official data. Constructed by this platform — not an official statistic.">
        <LivePulse at={data?.computed_at} />
      </PageHeader>
      {error && <p className="px-3 text-xs text-critical">{(error as Error).message}</p>}
      {isLoading && <p className="px-3 text-xs text-muted-foreground">Computing from latest data…</p>}
      {data && !data.available && <p className="px-3 text-xs text-warning">Unavailable: {data.reason}</p>}
      {data?.available && (
        <>
          <div className="grid grid-cols-1 gap-2 px-3 xl:grid-cols-[minmax(0,1fr)_minmax(0,2fr)]">
            <Panel title={`Score · ${data.period}`} subtitle={data.label}>
              <div className="flex items-end gap-3">
                <span className="text-5xl font-semibold leading-none tabular">{fmtNumber(data.score, 1)}</span>
                <span className="pb-1 text-[12px] text-muted-foreground">/ 100</span>
                <span className="ml-auto pb-1 text-right text-[11px]">
                  <span className="block font-medium capitalize">{data.band}</span>
                  <span className="text-muted-foreground">composite z = {fmtNumber(data.z, 2)}</span>
                </span>
              </div>
              <div className="mt-3 mb-5"><ScoreTrack score={data.score} /></div>
              <div className="grid grid-cols-3 gap-3">
                <Stat label={`vs ${data.previous_period ?? "previous"}`} value={<span className={(data.change_vs_previous ?? 0) >= 0 ? "text-cyan" : "text-serious"}>{fmtSigned(data.change_vs_previous)} pts</span>} />
                <Stat label="vs a year earlier" value={<span className={(data.change_vs_year_ago ?? 0) >= 0 ? "text-cyan" : "text-serious"}>{fmtSigned(data.change_vs_year_ago)} pts</span>} />
                <Stat label="Latest input release" value={fmtDateTime(data.latest_input_release).split(",")[0]} sub={`refreshed ${new Date(dataUpdatedAt).toLocaleTimeString("en-GB")}`} />
              </div>
              <div className="mt-3 grid grid-cols-2 gap-2">
                {PILLAR_ORDER.map((p) => {
                  const x = data.pillars.find((q) => q.id === p)!;
                  return (
                    <div key={p} className="rounded border bg-secondary/40 p-2">
                      <div className="flex items-center justify-between text-[11px]"><span>{x.label}</span>
                        <span className="tabular font-semibold">{x.score != null ? fmtNumber(x.score, 0) : "–"}</span></div>
                      <div className="mt-1.5 mb-3.5"><ScoreTrack score={x.score ?? 50} /></div>
                      <label className="flex items-center justify-between text-[10px] text-muted-foreground">Weight
                        <span className="inline-flex items-center gap-1">
                          <button aria-label={`Decrease ${x.label} weight`} onClick={() => setWeight(p, -0.5)} className="rounded border px-1.5 hover:bg-accent">−</button>
                          <span className="w-6 text-center tabular text-foreground">{weights[p]}</span>
                          <button aria-label={`Increase ${x.label} weight`} onClick={() => setWeight(p, 0.5)} className="rounded border px-1.5 hover:bg-accent">+</button>
                        </span>
                      </label>
                    </div>
                  );
                })}
              </div>
              {wParam && <p className="mt-2 text-[10px] text-warning">Custom weights in use (default is equal weights). <button className="underline" onClick={() => { const n = new URLSearchParams(sp.toString()); n.delete("w"); router.replace(`${pathname}?${n.toString()}`); }}>Reset</button></p>}
            </Panel>
            <Panel title="Score history" subtitle={`Monthly since ${data.history[0]?.period}. 50 = historical average (base ${data.method.base_window}). Uses current vintages of revised inputs.`}
              actions={<Seg value={showPillars} onChange={setShowPillars} label="Series" options={[{ value: "score", label: "Composite" }, { value: "pillars", label: "Pillars" }]} />}>
              <TimeSeriesChart series={series} unit="index" decimals={1} height={330} zoom yMin={0} yMax={100} baseline={50} />
            </Panel>
          </div>
          <div className="mt-2 grid grid-cols-1 gap-2 px-3 xl:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
            <Panel title="Components · what is driving the score" subtitle="Each input is a published series. z = standard deviations from its base-window mean after orienting so higher = more favourable. Contributions sum to the composite z.">
              <DataTable rows={data.components} rowKey={(c) => c.id} maxHeight={420}
                columns={[
                  { key: "p", header: "Pillar", value: (c) => c.pillar, render: (c) => data.pillars.find((x) => x.id === c.pillar)?.label },
                  { key: "t", header: "Component", value: (c) => c.title, render: (c) => <span title={c.transform}>{c.title}</span> },
                  { key: "i", header: "Source series", value: (c) => c.inputs.join(","), render: (c) => (
                    <span className="flex flex-wrap gap-1">{c.inputs.map((i) => (
                      <Link key={i} href={inv({ series: i, period: c.period_used ?? undefined })} className="text-cyan hover:underline">{data.inputs[i]?.title ?? i}</Link>))}</span>) },
                  { key: "v", header: "Value", align: "right", value: (c) => c.value ?? null, render: (c) => c.available ? fmtValue(c.value, c.unit === "number" ? "" : c.unit ?? "", c.unit === "number" ? 0 : 2) : <span className="text-muted-foreground">{c.reason}</span> },
                  { key: "pu", header: "Period", value: (c) => c.period_used ?? null, render: (c) => <span className={c.carried_forward ? "text-warning" : ""} title={c.carried_forward ? "Latest published value carried forward (max 3 months)" : undefined}>{c.period_used ?? "–"}{c.carried_forward ? " ↻" : ""}</span> },
                  { key: "d", header: "Direction", value: (c) => c.direction ?? "", render: (c) => <span className="text-[10px] text-muted-foreground">{c.direction}</span> },
                  { key: "z", header: "z", align: "right", value: (c) => c.z ?? null, render: (c) => <span className={cn((c.z ?? 0) >= 0 ? "text-cyan" : "text-serious")}>{fmtNumber(c.z, 2)}</span> },
                  { key: "c", header: "Contribution", align: "right", value: (c) => c.contribution_z ?? null, render: (c) => fmtNumber(c.contribution_z, 3) },
                ]} />
              <p className="mt-1 text-[10px] text-muted-foreground">↻ = latest published value carried forward to the scoring month (inputs are released on different days; max {String(data.method.max_carry_forward_months)} months).</p>
            </Panel>
            <Panel title="Contribution to composite z">
              <EChart option={contribOpt} height={300} ariaLabel="Contribution of each component to the score" />
            </Panel>
          </div>
          <div className="mt-2 grid grid-cols-1 gap-2 px-3 xl:grid-cols-2">
            <Panel title="Input freshness" subtitle="The score updates automatically when any of these is re-published and retrieved.">
              <DataTable rows={Object.entries(data.inputs).map(([id, x]) => ({ id, ...x }))} rowKey={(r) => r.id} maxHeight={300}
                columns={[
                  { key: "t", header: "Series", value: (r) => r.title, render: (r) => <Link href={inv({ series: r.id })} className="hover:text-primary">{r.title}</Link> },
                  { key: "pub", header: "Publisher", value: (r) => r.publisher },
                  { key: "lp", header: "Latest period", value: (r) => r.last_period },
                  { key: "rd", header: "Published", value: (r) => r.release_date, render: (r) => fmtDateTime(r.release_date) },
                  { key: "nr", header: "Next release", value: (r) => r.next_release ?? "" },
                ]} />
            </Panel>
            <Panel title="Method & caveats">
              <dl className="space-y-1 text-[11px]">
                {Object.entries(data.method).map(([k, v]) => (
                  <div key={k} className="grid grid-cols-[150px_minmax(0,1fr)] gap-2"><dt className="text-muted-foreground">{k.replaceAll("_", " ")}</dt><dd>{String(v)}</dd></div>
                ))}
              </dl>
              <ul className="mt-2 list-disc space-y-1 pl-4 text-[11px] text-warning">{data.caveats.map((c) => <li key={c}>{c}</li>)}</ul>
              <p className="mt-2 text-[10px] text-muted-foreground">Full description: docs/methodology.md §9. Bands: &lt;20 well below, 20–40 below, 40–60 around, 60–80 above, &gt;80 well above historical average.</p>
            </Panel>
          </div>
        </>
      )}
    </div>
  );
}
