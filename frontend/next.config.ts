import type { NextConfig } from "next";

// Client-rendered analytical UI over the FastAPI backend. Cache Components is not used (no `use cache`),
// so it is disabled to keep rendering semantics simple. `output: "standalone"` produces a small Docker image.
const nextConfig: NextConfig = {
  output: "standalone",
  // Browser talks to same-origin /api/*; Next proxies to the FastAPI service (no CORS, one public port).
  async rewrites() {
    const target = process.env.API_INTERNAL_URL || "http://localhost:8000";
    return [{ source: "/api/:path*", destination: `${target}/api/:path*` }];
  },
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
