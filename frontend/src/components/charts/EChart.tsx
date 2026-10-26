"use client";
// Thin ECharts wrapper: tree-shaken modules, canvas renderer, resize observer, click events,
// optional `group` so time-series charts share a synchronised crosshair (linked charts).
import { useEffect, useRef } from "react";
import * as echarts from "echarts/core";
import { BarChart, HeatmapChart, LineChart, ScatterChart } from "echarts/charts";
import {
  DataZoomComponent, GridComponent, LegendComponent, MarkAreaComponent, MarkLineComponent, MarkPointComponent,
  TooltipComponent, VisualMapComponent, AxisPointerComponent,
} from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import { LegacyGridContainLabel } from "echarts/features";
import type { EChartsCoreOption } from "echarts/core";

echarts.use([
  LineChart, BarChart, HeatmapChart, ScatterChart, GridComponent, TooltipComponent, LegendComponent,
  DataZoomComponent, MarkLineComponent, MarkAreaComponent, MarkPointComponent, VisualMapComponent,
  AxisPointerComponent, CanvasRenderer, LegacyGridContainLabel,
]);

export type ChartClick = { seriesIndex?: number; dataIndex?: number; data?: unknown; name?: string; value?: unknown };

export function EChart({
  option, height = 240, onClick, group, className, ariaLabel,
}: {
  option: EChartsCoreOption;
  height?: number | string;
  onClick?: (p: ChartClick) => void;
  group?: string;
  className?: string;
  ariaLabel?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const chart = useRef<echarts.ECharts | null>(null);
  const clickRef = useRef(onClick);
  useEffect(() => {
    clickRef.current = onClick;
  }, [onClick]);

  useEffect(() => {
    if (!ref.current) return;
    const c = echarts.init(ref.current, undefined, { renderer: "canvas" });
    chart.current = c;
    c.on("click", (p) => clickRef.current?.(p as ChartClick));
    const ro = new ResizeObserver(() => c.resize());
    ro.observe(ref.current);
    return () => {
      ro.disconnect();
      c.dispose();
      chart.current = null;
    };
  }, []);

  useEffect(() => {
    const c = chart.current;
    if (!c) return;
    c.setOption(option, { notMerge: true, lazyUpdate: true });
    if (group) {
      c.group = group;
      echarts.connect(group);
    }
  }, [option, group]);

  return (
    <div
      ref={ref}
      role="img"
      aria-label={ariaLabel}
      className={className}
      style={{ height, width: "100%", cursor: onClick ? "pointer" : undefined }}
    />
  );
}
