"use client";
// Choropleth of ITL1 regions or local authorities using MapLibre GL and ONS Open Geography boundaries
// (served by our API, cached). No third-party basemap by default: boundaries render on the dark plane, so
// the map works with zero external tile dependencies. Set NEXT_PUBLIC_BASEMAP_STYLE to add a free basemap.
import "maplibre-gl/dist/maplibre-gl.css";
import * as maplibregl from "maplibre-gl";
import type { GeoJSONSource, Map as MLMap, MapLayerMouseEvent } from "maplibre-gl";
import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { SEQ_BLUE } from "@/lib/colors";
import { fmtValue } from "@/lib/format";

maplibregl.setWorkerUrl("/maplibre-gl-worker.mjs");

type FC = GeoJSON.FeatureCollection<GeoJSON.Geometry, { code: string; name: string }>;

async function loadBoundaries(level: string): Promise<FC> {
  const r = await fetch(`/api/geo/boundaries/${level}`);
  if (!r.ok) throw new Error(r.status === 404 ? "Boundaries not retrieved yet (run the ons_geography source)" : r.statusText);
  return r.json();
}

function quantileBreaks(values: number[], k = 5): number[] {
  const v = [...values].sort((a, b) => a - b);
  if (!v.length) return [];
  return Array.from({ length: k - 1 }, (_, i) => v[Math.floor(((i + 1) / k) * (v.length - 1))]);
}

export interface MapDatum { code: string; value: number | null; label?: string }

export function RegionMap({
  level, data, unit, decimals = 1, selected, onSelect, height = 360, focusCodes, attribution,
}: {
  level: "itl1" | "lad";
  data: MapDatum[];
  unit: string;
  decimals?: number;
  selected?: string | null;
  onSelect?: (code: string, name: string) => void;
  height?: number;
  focusCodes?: string[] | null;
  attribution?: string;
}) {
  const container = useRef<HTMLDivElement>(null);
  const map = useRef<MLMap | null>(null);
  const [ready, setReady] = useState(false);
  const [hover, setHover] = useState<{ name: string; value: number | null; x: number; y: number } | null>(null);
  const { data: geo, error } = useQuery({ queryKey: ["boundaries", level], queryFn: () => loadBoundaries(level),
    staleTime: Infinity });
  const selectRef = useRef(onSelect);
  useEffect(() => {
    selectRef.current = onSelect;
  }, [onSelect]);

  const byCode = useMemo(() => new Map(data.map((d) => [d.code, d.value])), [data]);
  const breaks = useMemo(() => quantileBreaks(data.map((d) => d.value).filter((v): v is number => v != null)), [data]);
  const colorFor = (v: number | null | undefined) => {
    if (v == null) return "#1a222d";
    let i = 0;
    while (i < breaks.length && v > breaks[i]) i++;
    return SEQ_BLUE[i];
  };

  useEffect(() => {
    if (!container.current) return;
    const style = process.env.NEXT_PUBLIC_BASEMAP_STYLE || {
      version: 8 as const, sources: {}, layers: [{ id: "bg", type: "background" as const, paint: { "background-color": "#0b0f14" } }],
    };
    const m = new maplibregl.Map({
      container: container.current, style, center: [-3.2, 54.6], zoom: 4.3, attributionControl: false,
      dragRotate: false, pitchWithRotate: false, canvasContextAttributes: { preserveDrawingBuffer: true },
    });
    m.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    m.addControl(new maplibregl.AttributionControl({ compact: true, customAttribution:
      attribution ?? "Boundaries: ONS Open Geography, OGL v3.0. Contains OS data © Crown copyright and database right" }));
    m.on("load", () => {
      m.addSource("areas", { type: "geojson", data: { type: "FeatureCollection", features: [] }, promoteId: "code" });
      m.addLayer({ id: "fill", type: "fill", source: "areas", paint: { "fill-color": ["coalesce", ["get", "_c"], "#1a222d"], "fill-opacity": 0.92 } });
      m.addLayer({ id: "line", type: "line", source: "areas", paint: { "line-color": "#0b0f14", "line-width": level === "lad" ? 0.4 : 1 } });
      m.addLayer({ id: "sel", type: "line", source: "areas", filter: ["==", ["get", "code"], ""], paint: { "line-color": "#e8a33d", "line-width": 2 } });
      m.on("mousemove", "fill", (e: MapLayerMouseEvent) => {
        const f = e.features?.[0];
        if (!f) return;
        m.getCanvas().style.cursor = "pointer";
        setHover({ name: String(f.properties?.name), value: f.properties?._v ?? null, x: e.point.x, y: e.point.y });
      });
      m.on("mouseleave", "fill", () => { m.getCanvas().style.cursor = ""; setHover(null); });
      m.on("click", "fill", (e: MapLayerMouseEvent) => {
        const f = e.features?.[0];
        if (f) selectRef.current?.(String(f.properties?.code), String(f.properties?.name));
      });
      setReady(true);
    });
    map.current = m;
    if (process.env.NODE_ENV !== "production") (window as unknown as { __ukmap?: MLMap }).__ukmap = m;
    return () => { m.remove(); map.current = null; setReady(false); };
  }, [level, attribution]);

  useEffect(() => {
    const m = map.current;
    if (!m || !ready || !geo) return;
    const features = geo.features.map((f) => {
      const v = byCode.get(f.properties.code);
      return { ...f, properties: { ...f.properties, _v: v ?? null, _c: colorFor(v) } };
    });
    (m.getSource("areas") as GeoJSONSource).setData({ type: "FeatureCollection", features });
    const focus = focusCodes?.length ? features.filter((f) => focusCodes.includes(f.properties.code)) : null;
    const target = focus?.length ? focus : features;
    const b = new maplibregl.LngLatBounds();
    for (const f of target) {
      const walk = (c: unknown): void => {
        if (Array.isArray(c) && typeof c[0] === "number") b.extend(c as [number, number]);
        else if (Array.isArray(c)) c.forEach(walk);
      };
      walk((f.geometry as GeoJSON.Polygon).coordinates);
    }
    if (!b.isEmpty()) m.fitBounds(b, { padding: 16, duration: 300, maxZoom: 9 });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [geo, ready, byCode, breaks, focusCodes]);

  useEffect(() => {
    const m = map.current;
    if (m && ready) m.setFilter("sel", ["==", ["get", "code"], selected ?? ""]);
  }, [selected, ready]);

  const legend = [null, ...breaks].map((lo, i) => ({ color: SEQ_BLUE[i], lo, hi: breaks[i] ?? null }));
  return (
    <div className="relative" style={{ height }}>
      {/* MapLibre forces position:relative on its container, so size it explicitly rather than with inset-0. */}
      <div ref={container} className="w-full rounded" style={{ height }} aria-label="Regional choropleth map" role="application" />
      {error && <div className="absolute inset-0 flex items-center justify-center text-xs text-critical">{(error as Error).message}</div>}
      {hover && (
        <div className="pointer-events-none absolute z-10 rounded border bg-popover px-2 py-1 text-[11px] shadow-lg"
          style={{ left: hover.x + 12, top: hover.y + 12 }}>
          <div className="font-medium">{hover.name}</div>
          <div className="tabular text-muted-foreground">{fmtValue(hover.value, unit, decimals, false)}</div>
          <div className="text-[10px] text-muted-foreground">Click to select / drill down</div>
        </div>
      )}
      {breaks.length > 0 && (
        <div className="absolute bottom-2 left-2 rounded border bg-background/85 px-2 py-1.5 text-[10px]">
          <div className="mb-1 text-muted-foreground">Quintiles ({unit})</div>
          {legend.map((l, i) => (
            <div key={i} className="flex items-center gap-1.5 tabular">
              <span className="inline-block size-2.5 rounded-sm" style={{ background: l.color }} />
              {l.lo == null ? `≤ ${fmtValue(l.hi, unit, decimals)}` : l.hi == null ? `> ${fmtValue(l.lo, unit, decimals)}`
                : `${fmtValue(l.lo, unit, decimals)} – ${fmtValue(l.hi, unit, decimals)}`}
            </div>
          ))}
          <div className="flex items-center gap-1.5"><span className="inline-block size-2.5 rounded-sm bg-[#1a222d] border" />No data</div>
        </div>
      )}
    </div>
  );
}
