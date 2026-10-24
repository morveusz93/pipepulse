import type { PipelineOut } from "@/lib/types";
import { formatDuration, formatRelative, formatTimestamp, refLabel } from "@/lib/format";
import { FailedJobs } from "./FailedJobs";
import { LazyDetails } from "./LazyDetails";
import { StatusBadge } from "./StatusBadge";
import styles from "./PipelineTable.module.css";

export function PipelineTable({
  pipelines,
  defaultBranch,
  now,
  emptyMessage = "No pipelines recorded yet.",
}: {
  pipelines: PipelineOut[];
  defaultBranch: string | null;
  now: number;
  emptyMessage?: string;
}) {
  if (pipelines.length === 0) {
    return <div className={styles.empty}>{emptyMessage}</div>;
  }
  return (
    <div className={styles.table}>
      <div className={`${styles.row} ${styles.head}`}>
        <span>Status</span>
        <span>Pipeline</span>
        <span>Ref</span>
        <span>Commit</span>
        <span className={styles.num}>
          Duration
        </span>
        <span className={styles.num}>
          Created
        </span>
      </div>
      {pipelines.map((pipeline) => {
        const cells = <Cells pipeline={pipeline} defaultBranch={defaultBranch} now={now} />;
        if (pipeline.status !== "failed") {
          return (
            <div key={pipeline.id} className={styles.row}>
              {cells}
            </div>
          );
        }
        return (
          <LazyDetails
            key={pipeline.id}
            className={styles.failed}
            summaryClassName={`${styles.row} ${styles.expandable}`}
            summary={cells}
          >
            <div className={styles.expanded}>
              <FailedJobs jobs={pipeline.failed_jobs} initiallyOpen />
            </div>
          </LazyDetails>
        );
      })}
    </div>
  );
}

function Cells({
  pipeline,
  defaultBranch,
  now,
}: {
  pipeline: PipelineOut;
  defaultBranch: string | null;
  now: number;
}) {
  const onDefault = pipeline.ref === defaultBranch;
  return (
    <>
      <span className={styles.status}>
        <StatusBadge status={pipeline.status} />
        {pipeline.status === "failed" && <span className={styles.chevron} aria-hidden />}
      </span>
      <span className={`${styles.id} mono`}>
        #{pipeline.gitlab_pipeline_id}
      </span>
      <span>
        <span className={`${styles.ref} ${onDefault ? styles.refDefault : ""} mono`}>
          {refLabel(pipeline.ref)}
        </span>
      </span>
      <span className={styles.commit}>
        <span className={styles.title}>{pipeline.commit_title ?? "—"}</span>
        <span className={`${styles.sha} mono`}>{pipeline.sha.slice(0, 8)}</span>
      </span>
      <span className={`${styles.num} mono`}>
        {formatDuration(pipeline.duration_s)}
      </span>
      <span
       
        className={`${styles.num} ${styles.muted} mono`}
        title={`${formatTimestamp(pipeline.created_at)} UTC`}
      >
        {formatRelative(pipeline.created_at, now)}
      </span>
    </>
  );
}
