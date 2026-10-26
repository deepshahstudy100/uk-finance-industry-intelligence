"use client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bookmark, Search, X } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import {
  CommandDialog, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList,
} from "@/components/ui/command";
import { DropdownMenu, DropdownMenuContent, DropdownMenuGroup, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { api } from "@/lib/api";
import { useFilters } from "@/lib/filters";
import { useMeta, useOverview } from "@/lib/hooks";
import { STATUS_COLOR } from "@/lib/colors";
import { cn } from "@/lib/utils";

const SECTIONS: [string, string][] = [
  ["A", "Agriculture"], ["B", "Mining"], ["C", "Manufacturing"], ["D", "Energy supply"], ["E", "Water & waste"],
  ["F", "Construction"], ["G", "Wholesale & retail"], ["H", "Transport"], ["I", "Accommodation & food"],
  ["J", "Information & comms"], ["K", "Finance & insurance"], ["L", "Real estate"], ["M", "Professional services"],
  ["N", "Admin & support"], ["O", "Public admin"], ["P", "Education"], ["Q", "Health & social work"],
  ["R", "Arts & recreation"], ["S", "Other services"],
];

const PRESETS: { label: string; from: string | null }[] = [
  { label: "All", from: null },
  { label: "1Y", from: yearsAgo(1) },
  { label: "3Y", from: yearsAgo(3) },
  { label: "5Y", from: yearsAgo(5) },
  { label: "10Y", from: yearsAgo(10) },
  { label: "Since 2000", from: "2000" },
];

function yearsAgo(n: number) {
  const d = new Date();
  return `${d.getFullYear() - n}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

interface SearchResult { type: string; id: string; title: string; subtitle: string }

export function TopBar() {
  const { filters, set } = useFilters();
  const router = useRouter();
  const pathname = usePathname();
  const sp = useSearchParams();
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const { data: meta } = useMeta();
  const { data: ov } = useOverview();
  const { data: areas } = useQuery({
    queryKey: ["areas-top"],
    queryFn: () => api<{ code: string; name: string; level: string }[]>("/geo/areas"),
    staleTime: Infinity,
  });
  const { data: results } = useQuery({
    queryKey: ["search", q],
    queryFn: () => api<{ results: SearchResult[] }>(`/search?q=${encodeURIComponent(q)}`),
    enabled: q.trim().length > 0,
  });

  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((o) => !o);
      }
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, []);

  const go = (r: SearchResult) => {
    setOpen(false);
    if (r.type === "series") router.push(`/investigate?series=${r.id}`);
    else if (r.type === "geography") router.push(`/regions?geo=${r.id}`);
    else if (r.type === "industry") router.push(`/industry?sector=${r.id}`);
  };

  const nonLad = (areas ?? []).filter((a) => a.level !== "lad");
  const lads = (areas ?? []).filter((a) => a.level === "lad");
  const bad = (ov?.sources ?? []).filter((s) => ["unavailable", "stale", "degraded"].includes(s.status));
  const activePreset = PRESETS.find((p) => p.from === filters.from && !filters.to)?.label;

  return (
    <div className="shrink-0 border-b bg-background/95">
      <div className="flex flex-wrap items-center gap-2 px-3 py-1.5">
        <button
          onClick={() => setOpen(true)}
          className="flex h-7 w-full max-w-64 items-center gap-2 rounded border bg-secondary px-2 text-[11px] text-muted-foreground hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring outline-none"
          aria-label="Search metrics, places and industries"
        >
          <Search className="size-3.5" /> Search metrics, regions, industries…
          <kbd className="ml-auto rounded border px-1 text-[9px]">⌘K</kbd>
        </button>

        <div className="flex flex-wrap items-center gap-1" role="group" aria-label="Date range">
          <span className="text-[10px] uppercase tracking-wider text-muted-foreground">Range</span>
          <div className="inline-flex rounded border bg-secondary p-0.5">
            {PRESETS.map((p) => (
              <button key={p.label} onClick={() => set({ from: p.from, to: null })}
                aria-pressed={activePreset === p.label}
                className={cn("rounded-sm px-1.5 py-0.5 text-[11px]", activePreset === p.label
                  ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground")}>
                {p.label}
              </button>
            ))}
          </div>
          <input aria-label="From (YYYY-MM)" placeholder="from" value={filters.from ?? ""} onChange={(e) => set({ from: e.target.value || null })}
            pattern="\d{4}(-\d{2})?" className="h-7 w-[70px] rounded border bg-secondary px-1.5 text-[11px] tabular outline-none focus-visible:ring-2 focus-visible:ring-ring" />
          <input aria-label="To (YYYY-MM)" placeholder="to" value={filters.to ?? ""} onChange={(e) => set({ to: e.target.value || null })}
            className="h-7 w-[70px] rounded border bg-secondary px-1.5 text-[11px] tabular outline-none focus-visible:ring-2 focus-visible:ring-ring" />
        </div>

        <label className="flex items-center gap-1 text-[10px] uppercase tracking-wider text-muted-foreground">
          Geography
          <select value={filters.geo ?? ""} onChange={(e) => set({ geo: e.target.value || null })}
            className="h-7 max-w-44 rounded border bg-secondary px-1 text-[11px] normal-case tracking-normal text-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring">
            <option value="">United Kingdom (all)</option>
            <optgroup label="Nations & regions">
              {nonLad.filter((a) => a.code !== "K02000001").map((a) => <option key={a.code} value={a.code}>{a.name}</option>)}
            </optgroup>
            {lads.length > 0 && (
              <optgroup label="Local authorities">
                {lads.map((a) => <option key={a.code} value={a.code}>{a.name}</option>)}
              </optgroup>
            )}
          </select>
        </label>

        <label className="flex items-center gap-1 text-[10px] uppercase tracking-wider text-muted-foreground">
          Sector
          <select value={filters.sector ?? ""} onChange={(e) => set({ sector: e.target.value || null })}
            className="h-7 max-w-44 rounded border bg-secondary px-1 text-[11px] normal-case tracking-normal text-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring">
            <option value="">All industries</option>
            {SECTIONS.map(([k, v]) => <option key={k} value={k}>{k} · {v}</option>)}
          </select>
        </label>

        {(filters.from || filters.to || filters.geo || filters.sector) && (
          <button onClick={() => set({ from: null, to: null, geo: null, sector: null })}
            className="inline-flex items-center gap-1 rounded px-1.5 py-1 text-[11px] text-muted-foreground hover:text-foreground">
            <X className="size-3" /> Clear
          </button>
        )}

        <div className="ml-auto flex items-center gap-2">
          <SavedViews path={pathname} search={sp.toString()} />
          <button onClick={() => router.push("/sources")} className="flex items-center gap-1.5 rounded border px-2 py-1 text-[11px] text-muted-foreground hover:text-foreground"
            title="Source health">
            <span className="flex gap-0.5">
              {(ov?.sources ?? []).map((s) => (
                <span key={s.id} className="inline-block size-1.5 rounded-full" style={{ background: STATUS_COLOR[s.status] ?? "#8a96a8" }} />
              ))}
            </span>
            {bad.length ? `${bad.length} source issue${bad.length > 1 ? "s" : ""}` : "Sources OK"}
          </button>
        </div>
      </div>
      {meta && meta.demo_mode !== "off" && (
        <div className="flex items-center gap-2 border-t border-demo/30 bg-demo/5 px-3 py-0.5 text-[10px] text-demo demo-hatch">
          <b className="uppercase tracking-wider">Demo mode: {meta.demo_mode}</b>
          <span className="text-muted-foreground">
            {meta.demo_mode === "only" ? "All values are synthetic sample data." :
              "Series with no retrieved real data show labelled synthetic sample data. Real data always takes precedence and is never mixed with samples."}
          </span>
        </div>
      )}

      <CommandDialog open={open} onOpenChange={setOpen} title="Search" description="Search metrics, places and industries">
        <CommandInput placeholder="e.g. inflation, manufacturing, Manchester, gilt…" value={q} onValueChange={setQ} />
        <CommandList>
          <CommandEmpty>{q ? "No matches." : "Type to search the catalogue."}</CommandEmpty>
          {(["series", "geography", "industry"] as const).map((t) => {
            const rs = (results?.results ?? []).filter((r) => r.type === t);
            if (!rs.length) return null;
            return (
              <CommandGroup key={t} heading={t === "series" ? "Metrics" : t === "geography" ? "Places" : "Industries"}>
                {rs.map((r) => (
                  <CommandItem key={`${r.type}:${r.id}`} value={`${r.title} ${r.id}`} onSelect={() => go(r)}>
                    <div className="flex min-w-0 flex-col">
                      <span className="truncate text-[12px]">{r.title}</span>
                      <span className="truncate text-[10px] text-muted-foreground">{r.subtitle}</span>
                    </div>
                  </CommandItem>
                ))}
              </CommandGroup>
            );
          })}
        </CommandList>
      </CommandDialog>
    </div>
  );
}

function SavedViews({ path, search }: { path: string; search: string }) {
  const qc = useQueryClient();
  const router = useRouter();
  const { data: views } = useQuery({
    queryKey: ["views"],
    queryFn: () => api<{ id: number; name: string; path: string }[]>("/views"),
  });
  const save = useMutation({
    mutationFn: (name: string) => api("/views", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, path: search ? `${path}?${search}` : path }),
    }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["views"] }),
  });
  const del = useMutation({
    mutationFn: (id: number) => api(`/views/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["views"] }),
  });
  return (
    <DropdownMenu>
      <DropdownMenuTrigger className="inline-flex items-center gap-1 rounded border px-2 py-1 text-[11px] text-muted-foreground hover:text-foreground">
        <Bookmark className="size-3.5" /> Views
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-64">
        <DropdownMenuItem onClick={() => {
          const name = window.prompt("Name this view (page + filters)");
          if (name) save.mutate(name);
        }}>Save current view…</DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuGroup>
        <DropdownMenuLabel className="text-[10px]">Saved views</DropdownMenuLabel>
        {(views ?? []).map((v) => (
          <DropdownMenuItem key={v.id} onClick={() => router.push(v.path)} className="flex justify-between gap-2">
            <span className="truncate">{v.name}</span>
            <span role="button" aria-label={`Delete ${v.name}`} className="text-muted-foreground hover:text-critical"
              onClick={(e) => { e.stopPropagation(); del.mutate(v.id); }}><X className="size-3" /></span>
          </DropdownMenuItem>
        ))}
        {!views?.length && <div className="px-2 py-1.5 text-[11px] text-muted-foreground">None yet</div>}
        </DropdownMenuGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
