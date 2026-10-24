import Link from "next/link";
import { hrefWith, type SearchParams } from "@/lib/query";
import { Segmented } from "./Segmented";
import styles from "./PipelineFilters.module.css";

export const STATUS_FILTERS = ["all", "failed", "success", "canceled"] as const;
export const SCOPE_FILTERS = ["all", "default"] as const;
export const SOURCE_FILTERS = ["all", "push", "merge_request_event", "schedule"] as const;
export const SORTS = ["-created_at", "-duration"] as const;

export interface PipelineFilterState {
  status: (typeof STATUS_FILTERS)[number];
  scope: (typeof SCOPE_FILTERS)[number];
  source: (typeof SOURCE_FILTERS)[number];
  sort: (typeof SORTS)[number];
  page: number;
}

const LABELS: Record<string, string> = {
  all: "All",
  failed: "Failed",
  success: "Passed",
  canceled: "Canceled",
  push: "Push",
  merge_request_event: "MR",
  schedule: "Schedule",
  "-created_at": "Newest",
  "-duration": "Slowest",
};

export function PipelineFilters({
  params,
  state,
  defaultBranch,
}: {
  params: SearchParams;
  state: PipelineFilterState;
  defaultBranch: string | null;
}) {
  // Every filter change starts over at page 1; "all" and other defaults stay out of the URL.
  const option = (key: keyof PipelineFilterState, value: string, fallback: string, label?: string) => ({
    label: label ?? LABELS[value],
    href: hrefWith(params, { [key]: value === fallback ? null : value, page: null }),
    current: state[key] === value,
  });

  const filtered =
    state.status !== "all" || state.scope !== "all" || state.source !== "all" || state.sort !== "-created_at";

  return (
    <div className={styles.bar}>
      <Segmented label="Status" options={STATUS_FILTERS.map((v) => option("status", v, "all"))} />
      <Segmented
        label="Refs"
        options={[
          option("scope", "all", "all", "All refs"),
          option("scope", "default", "all", defaultBranch ?? "Default branch"),
        ]}
      />
      <Segmented label="Source" options={SOURCE_FILTERS.map((v) => option("source", v, "all"))} />
      <Segmented label="Sort" options={SORTS.map((v) => option("sort", v, "-created_at"))} />
      {filtered && (
        <Link
          href={hrefWith(params, { status: null, scope: null, source: null, sort: null, page: null })}
          className={styles.clear}
          scroll={false}
        >
          Clear filters
        </Link>
      )}
    </div>
  );
}

export function Pagination({
  params,
  page,
  pageSize,
  total,
}: {
  params: SearchParams;
  page: number;
  pageSize: number;
  total: number;
}) {
  if (total <= pageSize) return null;
  const from = (page - 1) * pageSize + 1;
  const to = Math.min(page * pageSize, total);
  const pages = Math.ceil(total / pageSize);

  return (
    <nav className={styles.pagination} aria-label="Pipeline pages">
      <span className={`${styles.range} mono`}>
        {from}–{to} of {total}
      </span>
      <span className={styles.pageLinks}>
        {page > 1 ? (
          <Link
            href={hrefWith(params, { page: page === 2 ? null : String(page - 1) })}
            className={styles.pageLink}
            scroll={false}
          >
            ← Newer
          </Link>
        ) : (
          <span className={`${styles.pageLink} ${styles.disabled}`}>← Newer</span>
        )}
        {page < pages ? (
          <Link
            href={hrefWith(params, { page: String(page + 1) })}
            className={styles.pageLink}
            scroll={false}
          >
            Older →
          </Link>
        ) : (
          <span className={`${styles.pageLink} ${styles.disabled}`}>Older →</span>
        )}
      </span>
    </nav>
  );
}
