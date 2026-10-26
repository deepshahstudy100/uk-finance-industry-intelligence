import { Suspense } from "react";
import { View } from "./View";

export default function Page() {
  return (
    <Suspense fallback={<div className="p-4 text-xs text-muted-foreground">Loading…</div>}>
      <View />
    </Suspense>
  );
}
