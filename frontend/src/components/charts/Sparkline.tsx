// Lightweight SVG sparkline (no axes; the tile it sits in states value, unit and period).
export function Sparkline({ values, color = "#3fb6d3", width = 96, height = 26 }: {
  values: (number | null)[]; color?: string; width?: number; height?: number;
}) {
  const v = values.filter((x): x is number => x !== null && Number.isFinite(x));
  if (v.length < 2) return <svg width={width} height={height} aria-hidden />;
  const min = Math.min(...v);
  const max = Math.max(...v);
  const span = max - min || 1;
  const pts: string[] = [];
  let i = 0;
  values.forEach((x, k) => {
    if (x === null || !Number.isFinite(x)) return;
    const px = (k / (values.length - 1)) * (width - 4) + 2;
    const py = height - 3 - ((x - min) / span) * (height - 6);
    pts.push(`${i === 0 ? "M" : "L"}${px.toFixed(1)},${py.toFixed(1)}`);
    i++;
  });
  const last = pts[pts.length - 1]?.slice(1).split(",").map(Number);
  return (
    <svg width={width} height={height} aria-hidden className="overflow-visible">
      <path d={pts.join(" ")} fill="none" stroke={color} strokeWidth={1.5} strokeLinejoin="round" />
      {last && <circle cx={last[0]} cy={last[1]} r={2.2} fill={color} />}
    </svg>
  );
}
