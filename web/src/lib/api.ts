import "server-only";

import { DEMO_ENABLED, DemoNotFound, demoGet } from "./demo";

// Server components talk to the API directly; the browser goes through the /api rewrite.
const API_URL = process.env.PIPEPULSE_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly path: string,
  ) {
    super(`API ${path} responded ${status}`);
  }
}

export async function apiGet<T>(path: string, params?: Record<string, string | number>): Promise<T> {
  if (DEMO_ENABLED) {
    try {
      return (await demoGet(path, params)) as T;
    } catch (error) {
      if (error instanceof DemoNotFound) throw new ApiError(404, path);
      throw error;
    }
  }
  const query = params
    ? `?${new URLSearchParams(Object.entries(params).map(([k, v]) => [k, String(v)]))}`
    : "";
  const response = await fetch(`${API_URL}${path}${query}`, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    throw new ApiError(response.status, path);
  }
  return response.json() as Promise<T>;
}
