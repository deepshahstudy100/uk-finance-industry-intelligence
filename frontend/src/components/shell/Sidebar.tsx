"use client";
import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import {
  Activity, AlertTriangle, Building2, Database, Factory, Flame, Gauge, GitCompare, Home, Landmark, LayoutGrid,
  LineChart, Map, Ship, Telescope,
} from "lucide-react";
import { filterQuery } from "@/lib/filters";
import { cn } from "@/lib/utils";

export const NAV = [
  { href: "/", label: "Command centre", icon: LayoutGrid },
  { href: "/score", label: "Economic score", icon: Gauge },
  { href: "/macro", label: "National economy", icon: Activity },
  { href: "/industry", label: "Industry", icon: Factory },
  { href: "/markets", label: "Markets & rates", icon: LineChart },
  { href: "/regions", label: "Regions", icon: Map },
  { href: "/trade", label: "Trade", icon: Ship },
  { href: "/public-finance", label: "Public finance", icon: Landmark },
  { href: "/energy", label: "Energy", icon: Flame },
  { href: "/housing", label: "Housing", icon: Home },
  { href: "/companies", label: "Companies", icon: Building2 },
  { href: "/compare", label: "Compare & correlate", icon: GitCompare },
  { href: "/investigate", label: "Investigate", icon: Telescope },
  { href: "/alerts", label: "Alerts", icon: AlertTriangle },
  { href: "/sources", label: "Sources & health", icon: Database },
];

export function Sidebar() {
  const pathname = usePathname();
  const sp = useSearchParams();
  const q = filterQuery(sp);
  return (
    <nav aria-label="Modules" className="flex h-full w-12 shrink-0 flex-col items-center gap-0.5 border-r bg-sidebar py-2 lg:w-48 lg:items-stretch lg:px-2">
      <Link href="/" className="mb-3 flex items-center gap-2 px-1 py-1" aria-label="UK Intelligence home">
        <span className="grid size-7 place-items-center rounded border border-primary/50 bg-primary/10 text-[11px] font-bold text-primary">UK</span>
        <span className="hidden text-[11px] font-semibold leading-tight tracking-wide text-foreground lg:block">
          National Finance &amp;<br />Industry Intelligence
        </span>
      </Link>
      {NAV.map(({ href, label, icon: Icon }) => {
        const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
        return (
          <Link
            key={href}
            href={q && href !== "/investigate" ? `${href}?${q}` : href}
            title={label}
            aria-current={active ? "page" : undefined}
            className={cn("flex items-center gap-2.5 rounded px-2 py-1.5 text-[12px] outline-none focus-visible:ring-2 focus-visible:ring-ring",
              active ? "bg-sidebar-accent text-foreground shadow-[inset_2px_0_0_var(--primary)]"
                : "text-sidebar-foreground/80 hover:bg-sidebar-accent/60 hover:text-foreground")}
          >
            <Icon className={cn("size-4 shrink-0", active && "text-primary")} />
            <span className="hidden truncate lg:block">{label}</span>
          </Link>
        );
      })}
      <div className="mt-auto hidden px-2 pt-3 text-[9px] leading-snug text-muted-foreground lg:block">
        Open data only · no paid APIs.<br />Analytical design inspired by Foundry/Gotham; not affiliated with Palantir.
      </div>
    </nav>
  );
}
