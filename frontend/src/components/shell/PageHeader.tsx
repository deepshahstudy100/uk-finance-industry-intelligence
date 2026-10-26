export function PageHeader({ title, description, children }: {
  title: string; description?: React.ReactNode; children?: React.ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-2 px-3 pt-3 pb-2">
      <div className="min-w-0">
        <h1 className="text-[15px] font-semibold tracking-wide">{title}</h1>
        {description && <p className="max-w-4xl text-[11px] text-muted-foreground">{description}</p>}
      </div>
      {children && <div className="flex flex-wrap items-center gap-2">{children}</div>}
    </div>
  );
}

/** Wrap client views that read URL search params (required for prerendering in this Next.js version). */
export function PageShell({ children }: { children: React.ReactNode }) {
  return <div className="pb-6">{children}</div>;
}
