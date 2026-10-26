"use client";
import Link from "next/link";
import { Maximize2, Search } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

/** Dense analytical panel: hairline border, compact header with title, subtitle (source), actions. */
export function Panel({
  title, subtitle, actions, children, className, bodyClassName, investigate, demo, loading, error, empty,
}: {
  title: React.ReactNode;
  subtitle?: React.ReactNode;
  actions?: React.ReactNode;
  children?: React.ReactNode;
  className?: string;
  bodyClassName?: string;
  investigate?: string;
  demo?: boolean;
  loading?: boolean;
  error?: string | null;
  empty?: string | null;
}) {
  return (
    <section className={cn("flex min-w-0 flex-col rounded-md border bg-card", demo && "border-demo/40", className)}>
      <header className="flex items-center gap-2 border-b bg-panel-header/60 px-3 py-1.5 min-h-9">
        <div className="min-w-0 flex-1">
          <h2 className="truncate text-[12px] font-semibold tracking-wide text-foreground">{title}</h2>
          {subtitle && <p className="truncate text-[10px] text-muted-foreground">{subtitle}</p>}
        </div>
        {actions}
        {investigate && (
          <Link href={investigate} title="Investigate" aria-label="Open in investigation workspace"
            className="rounded p-1 text-muted-foreground hover:bg-accent hover:text-foreground">
            <Maximize2 className="size-3.5" />
          </Link>
        )}
      </header>
      <div className={cn("min-h-0 flex-1 p-2", bodyClassName)}>
        {loading ? (
          <div className="space-y-2 p-1"><Skeleton className="h-4 w-1/3" /><Skeleton className="h-32 w-full" /></div>
        ) : error ? (
          <div className="flex items-start gap-2 rounded border border-critical/30 bg-critical/5 p-2 text-xs text-critical">
            <span className="font-semibold">Unavailable:</span> <span className="text-muted-foreground">{error}</span>
          </div>
        ) : empty ? (
          <div className="flex h-full min-h-20 items-center justify-center gap-2 text-xs text-muted-foreground">
            <Search className="size-3.5" /> {empty}
          </div>
        ) : (
          children
        )}
      </div>
    </section>
  );
}

export function Stat({ label, value, sub }: { label: string; value: React.ReactNode; sub?: React.ReactNode }) {
  return (
    <div className="min-w-0">
      <div className="text-[10px] uppercase tracking-wider text-muted-foreground">{label}</div>
      <div className="truncate text-sm font-medium text-foreground tabular">{value}</div>
      {sub && <div className="truncate text-[10px] text-muted-foreground">{sub}</div>}
    </div>
  );
}

export function NativeSelect({ value, onChange, options, label, className }: {
  value: string; onChange: (v: string) => void; options: { value: string; label: string }[]; label: string;
  className?: string;
}) {
  return (
    <label className={cn("inline-flex items-center gap-1.5 text-[11px] text-muted-foreground", className)}>
      <span className="whitespace-nowrap">{label}</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="h-7 max-w-56 rounded border bg-secondary px-1.5 text-[11px] text-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
    </label>
  );
}

export function Seg<T extends string>({ value, onChange, options, label }: {
  value: T; onChange: (v: T) => void; options: { value: T; label: string; disabled?: boolean; title?: string }[];
  label?: string;
}) {
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex rounded border bg-secondary p-0.5">
      {options.map((o) => (
        <button
          key={o.value}
          role="radio"
          aria-checked={value === o.value}
          disabled={o.disabled}
          title={o.title}
          onClick={() => onChange(o.value)}
          className={cn("rounded-sm px-2 py-0.5 text-[11px] transition-colors disabled:cursor-not-allowed disabled:opacity-35",
            value === o.value ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground")}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}
