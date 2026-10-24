import type { NextConfig } from "next";

// Frontend-only public demo: data comes from src/demo/snapshot.json, there is no backend.
const demo = process.env.PIPEPULSE_DEMO === "true";

// Where browser calls to /api are proxied in dev and docker-compose. In Kubernetes the Ingress
// routes /api to the API service before requests reach Next.js, so this is never used there.
// Read at build time (the standalone server bakes rewrites in).
const apiUrl = process.env.PIPEPULSE_API_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  // Self-contained server for the Docker image; Vercel builds Next.js its own way.
  output: process.env.VERCEL ? undefined : "standalone",
  cacheComponents: true,
  partialPrefetching: true,
  reactCompiler: true,
  // The snapshot is read with fs at runtime; make sure it ships with the server output.
  outputFileTracingIncludes: { "/**": ["./src/demo/snapshot.json"] },
  async rewrites() {
    return demo ? [] : [{ source: "/api/:path*", destination: `${apiUrl}/api/:path*` }];
  },
};

export default nextConfig;
