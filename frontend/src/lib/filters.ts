"use client";
// Global filters live in the URL so every view is shareable, saveable and survives drill-down and back.
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useMemo } from "react";

export interface Filters {
  from: string | null; // YYYY or YYYY-MM
  to: string | null;
  geo: string | null; // GSS code
  sector: string | null; // SIC 2007 section letter
}

export const FILTER_KEYS = ["from", "to", "geo", "sector"] as const;

export function useFilters() {
  const sp = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const filters: Filters = useMemo(
    () => ({ from: sp.get("from"), to: sp.get("to"), geo: sp.get("geo"), sector: sp.get("sector") }),
    [sp],
  );
  const set = useCallback(
    (patch: Partial<Record<string, string | null>>) => {
      const next = new URLSearchParams(sp.toString());
      for (const [k, v] of Object.entries(patch)) {
        if (v === null || v === undefined || v === "") next.delete(k);
        else next.set(k, v);
      }
      const q = next.toString();
      router.replace(q ? `${pathname}?${q}` : pathname, { scroll: false });
    },
    [sp, router, pathname],
  );
  return { filters, set, params: sp };
}

/** Query string carrying only the global filters (used when linking between modules). */
export function filterQuery(sp: URLSearchParams | { get(k: string): string | null }): string {
  const u = new URLSearchParams();
  for (const k of FILTER_KEYS) {
    const v = sp.get(k);
    if (v) u.set(k, v);
  }
  return u.toString();
}

/** Link to the investigation workspace for one data point, preserving filters and a return path. */
export function investigateHref(
  target: { series: string; geo?: string | null; dim?: string | null; period?: string | null },
  current?: { pathname: string; search: string },
): string {
  const u = new URLSearchParams();
  u.set("series", target.series);
  if (target.geo) u.set("geo", target.geo);
  if (target.dim && target.dim !== "_") u.set("dim", target.dim);
  if (target.period) u.set("period", target.period);
  if (current) {
    const cur = new URLSearchParams(current.search);
    for (const k of ["from", "to", "sector"] as const) {
      const v = cur.get(k);
      if (v) u.set(k, v);
    }
    if (!target.geo && cur.get("geo")) u.set("fgeo", cur.get("geo")!);
    u.set("return", current.pathname + (current.search ? `?${current.search}` : ""));
  }
  return `/investigate?${u.toString()}`;
}

export function fromToDates(f: Filters): { start: string | null; end: string | null } {
  return { start: f.from, end: f.to };
}
