// MapLibre computes its worker URL relative to its own module; bundlers relocate that module, so we serve the
// self-contained worker build from /public and point maplibregl.setWorkerUrl() at it (see RegionMap.tsx).
import { copyFileSync, existsSync, mkdirSync } from "node:fs";
const src = "node_modules/maplibre-gl/dist/maplibre-gl-worker.mjs";
if (existsSync(src)) {
  mkdirSync("public", { recursive: true });
  copyFileSync(src, "public/maplibre-gl-worker.mjs");
  console.log("copied maplibre worker -> public/maplibre-gl-worker.mjs");
}
