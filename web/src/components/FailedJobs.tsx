"use client";

import { useState } from "react";
import type { JobLog, JobOut } from "@/lib/types";
import { formatDuration } from "@/lib/format";
import { LogViewer } from "./LogViewer";
import styles from "./FailedJobs.module.css";

type LogState =
  | { state: "idle" }
  | { state: "loading" }
  | { state: "loaded"; log: string | null }
  | { state: "error" };

/** Failed jobs as native accordions; each log is fetched the first time it's opened. */
export function FailedJobs({ jobs, initiallyOpen = false }: { jobs: JobOut[]; initiallyOpen?: boolean }) {
  if (jobs.length === 0) {
    return <p className={styles.note}>No failed job details were recorded for this pipeline.</p>;
  }
  return (
    <div className={styles.jobs}>
      {jobs.map((job, i) => (
        <JobDetails key={job.id} job={job} initiallyOpen={initiallyOpen && i === 0} />
      ))}
    </div>
  );
}

function JobDetails({ job, initiallyOpen }: { job: JobOut; initiallyOpen: boolean }) {
  const [log, setLog] = useState<LogState>({ state: "idle" });

  async function load() {
    if (log.state !== "idle") return;
    setLog({ state: "loading" });
    try {
      const response = await fetch(`/api/jobs/${job.id}/log`);
      if (!response.ok) throw new Error(String(response.status));
      const body = (await response.json()) as JobLog;
      setLog({ state: "loaded", log: body.log });
    } catch {
      setLog({ state: "error" });
    }
  }

  return (
    <details
      className={styles.job}
      open={initiallyOpen}
      onToggle={(event) => {
        if (event.currentTarget.open) void load();
      }}
    >
      <summary className={styles.summary}>
        <span className={styles.chevron} aria-hidden />
        <span className={styles.name}>{job.name}</span>
        <span className={styles.meta}>
          {job.stage}
          {job.failure_reason && <> · {job.failure_reason.replaceAll("_", " ")}</>}
        </span>
        <span className={`${styles.duration} mono`}>{formatDuration(job.duration_s)}</span>
      </summary>
      <div className={styles.body}>
        {log.state === "loading" || log.state === "idle" ? (
          <p className={styles.note}>Loading log…</p>
        ) : log.state === "error" ? (
          <p className={styles.note}>Couldn&apos;t load the log. Try again in a moment.</p>
        ) : log.log === null ? (
          <p className={styles.note}>
            GitLab didn&apos;t return this job&apos;s log. Logs require an authenticated token
            and may have expired.
          </p>
        ) : (
          <LogViewer log={log.log} label={`Log of job ${job.name}`} />
        )}
      </div>
    </details>
  );
}
