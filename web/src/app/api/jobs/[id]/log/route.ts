import { ApiError, apiGet } from "@/lib/api";
import type { JobLog } from "@/lib/types";

/**
 * Job logs requested by the browser (expanding a failed job). Served here rather than by the
 * /api rewrite so the frontend-only demo can answer it from its snapshot. In Kubernetes the
 * Ingress sends /api to FastAPI before requests reach Next.js, so this route isn't hit there.
 */
export async function GET(_request: Request, ctx: RouteContext<"/api/jobs/[id]/log">) {
  const { id } = await ctx.params;
  try {
    return Response.json(await apiGet<JobLog>(`/api/jobs/${encodeURIComponent(id)}/log`));
  } catch (error) {
    const status = error instanceof ApiError ? error.status : 502;
    return Response.json({ detail: "Job log unavailable" }, { status });
  }
}
