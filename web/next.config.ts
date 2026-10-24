import type { NextConfig } from "next";

const apiUrl = process.env.PIPEPULSE_API_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  cacheComponents: true,
  partialPrefetching: true,
  reactCompiler: true,
  // Browser calls to /api go to the FastAPI backend, so there's no CORS to configure.
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${apiUrl}/api/:path*` }];
  },
};

export default nextConfig;
