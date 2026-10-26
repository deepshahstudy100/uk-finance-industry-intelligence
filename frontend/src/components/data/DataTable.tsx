"use client";
import { ArrowDown, ArrowUp, ArrowUpDown } from "lucide-react";
import { useMemo, useState } from "react";
import { cn } from "@/lib/utils";

export interface Column<T> {
  key: string;
  header: string;
  value: (r: T) => string | number | null | undefined;
  render?: (r: T) => React.ReactNode;
  align?: "left" | "right";
  className?: string;
}

/** Dense sortable table. Rows are clickable (keyboard: Enter) when onRowClick is given. */
export function DataTable<T>({
  rows, columns, onRowClick, initialSort, maxHeight = 360, rowKey, selectedKey, caption,
}: {
  rows: T[];
  columns: Column<T>[];
  onRowClick?: (r: T) => void;
  initialSort?: { key: string; dir: "asc" | "desc" };
  maxHeight?: number | string;
  rowKey: (r: T) => string;
  selectedKey?: string | null;
  caption?: string;
}) {
  const [sort, setSort] = useState(initialSort ?? null);
  const sorted = useMemo(() => {
    if (!sort) return rows;
    const col = columns.find((c) => c.key === sort.key);
    if (!col) return rows;
    return [...rows].sort((a, b) => {
      const va = col.value(a);
      const vb = col.value(b);
      if (va == null && vb == null) return 0;
      if (va == null) return 1;
      if (vb == null) return -1;
      const c = typeof va === "number" && typeof vb === "number" ? va - vb : String(va).localeCompare(String(vb));
      return sort.dir === "asc" ? c : -c;
    });
  }, [rows, sort, columns]);
  return (
    <div className="overflow-auto rounded border" style={{ maxHeight }}>
      <table className="w-full border-collapse text-[11px]">
        {caption && <caption className="sr-only">{caption}</caption>}
        <thead className="sticky top-0 z-10 bg-panel-header">
          <tr>
            {columns.map((c) => {
              const active = sort?.key === c.key;
              const Icon = !active ? ArrowUpDown : sort!.dir === "asc" ? ArrowUp : ArrowDown;
              return (
                <th key={c.key} scope="col" aria-sort={active ? (sort!.dir === "asc" ? "ascending" : "descending") : "none"}
                  className={cn("border-b px-2 py-1.5 font-medium text-muted-foreground whitespace-nowrap",
                    c.align === "right" ? "text-right" : "text-left")}>
                  <button
                    className="inline-flex items-center gap-1 hover:text-foreground"
                    onClick={() => setSort({ key: c.key, dir: active && sort!.dir === "desc" ? "asc" : "desc" })}
                  >
                    {c.header} <Icon className="size-3 opacity-60" />
                  </button>
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {sorted.map((r) => {
            const k = rowKey(r);
            return (
              <tr
                key={k}
                tabIndex={onRowClick ? 0 : undefined}
                onClick={onRowClick ? () => onRowClick(r) : undefined}
                onKeyDown={onRowClick ? (e) => e.key === "Enter" && onRowClick(r) : undefined}
                className={cn("border-b border-border/60 last:border-0",
                  onRowClick && "cursor-pointer hover:bg-accent/60 focus-visible:bg-accent outline-none",
                  selectedKey === k && "bg-primary/10")}
              >
                {columns.map((c) => (
                  <td key={c.key} className={cn("px-2 py-1 tabular", c.align === "right" && "text-right", c.className)}>
                    {c.render ? c.render(r) : (c.value(r) ?? "–")}
                  </td>
                ))}
              </tr>
            );
          })}
          {!sorted.length && (
            <tr><td colSpan={columns.length} className="px-2 py-6 text-center text-muted-foreground">No rows</td></tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
