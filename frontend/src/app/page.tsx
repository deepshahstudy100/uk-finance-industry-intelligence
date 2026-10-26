import { Suspense } from "react";
import { CommandCentre } from "./CommandCentre";

export default function Page() {
  return (
    <Suspense fallback={<div className="p-4 text-xs text-muted-foreground">Loading command centre…</div>}>
      <CommandCentre />
    </Suspense>
  );
}
