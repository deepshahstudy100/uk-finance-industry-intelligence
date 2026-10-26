import { Suspense } from "react";
import { Workspace } from "@/components/workspace/Workspace";

export default function Page() {
  return (
    <Suspense fallback={<div className="p-4 text-xs text-muted-foreground">Loading workspace…</div>}>
      <Workspace />
    </Suspense>
  );
}
