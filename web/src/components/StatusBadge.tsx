import { statusTone } from "@/lib/format";
import styles from "./StatusBadge.module.css";

const LABELS: Record<string, string> = {
  success: "passed",
  failed: "failed",
  running: "running",
  pending: "pending",
  created: "created",
  preparing: "preparing",
  waiting_for_resource: "waiting",
  canceled: "canceled",
  skipped: "skipped",
  manual: "manual",
  scheduled: "scheduled",
};

export function StatusBadge({ status }: { status: string }) {
  const tone = statusTone(status);
  return (
    <span className={`${styles.badge} ${styles[tone]}`}>
      <span className={styles.dot} aria-hidden />
      {LABELS[status] ?? status}
    </span>
  );
}
