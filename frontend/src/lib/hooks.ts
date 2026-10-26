"use client";
import { useQuery } from "@tanstack/react-query";
import { usePathname, useSearchParams } from "next/navigation";
import { useCallback } from "react";
import {
  api, qs, type Analysis, type Meta, type ObservationsResponse, type Overview, type SeriesDetail,
  type SeriesSummary, type Slice,
} from "./api";
import { investigateHref } from "./filters";

export const useMeta = () => useQuery({ queryKey: ["meta"], queryFn: () => api<Meta>("/meta"), staleTime: 300_000 });
export const useOverview = () =>
  useQuery({ queryKey: ["overview"], queryFn: () => api<Overview>("/overview"), refetchInterval: 120_000 });

export const useSeriesList = (category?: string) =>
  useQuery({ queryKey: ["series", category], queryFn: () => api<SeriesSummary[]>(`/series${qs({ category })}`) });

export const useSeriesDetail = (id: string | null) =>
  useQuery({ queryKey: ["series-detail", id], queryFn: () => api<SeriesDetail>(`/series/${id}`), enabled: !!id });

export function useObservations(id: string | null, p: { geo?: string | null; dim?: string | null; start?: string | null;
  end?: string | null } = {}) {
  return useQuery({
    queryKey: ["obs", id, p],
    queryFn: () => api<ObservationsResponse>(`/series/${id}/observations${qs(p)}`),
    enabled: !!id,
  });
}

export function useAnalysis(id: string | null, p: { geo?: string | null; dim?: string | null; start?: string | null;
  end?: string | null; window?: number; related?: boolean } = {}) {
  return useQuery({
    queryKey: ["analysis", id, p],
    queryFn: () => api<Analysis>(`/series/${id}/analysis${qs(p)}`),
    enabled: !!id,
  });
}

export function useSlice(id: string | null, p: { by: "geo" | "dim"; period?: string | null; geo?: string | null;
  dim?: string | null; level?: string | null }) {
  return useQuery({
    queryKey: ["slice", id, p],
    queryFn: () => api<Slice>(`/series/${id}/slice${qs(p)}`),
    enabled: !!id,
  });
}

/** Returns a function producing an investigation link that remembers where the user came from. */
export function useInvestigate() {
  const pathname = usePathname();
  const sp = useSearchParams();
  return useCallback(
    (t: { series: string; geo?: string | null; dim?: string | null; period?: string | null }) =>
      investigateHref(t, { pathname, search: sp.toString() }),
    [pathname, sp],
  );
}
