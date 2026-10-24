import type { Incident } from "@/lib/types";
import { formatDuration, formatTimestamp } from "@/lib/format";
import styles from "./Incidents.module.css";

const SHOWN = 6;

/** Red streaks on the default branch, newest first: what MTTR is computed from. */
export function Incidents({ incidents, now }: { incidents: Incident[]; now: number }) {
  if (incidents.length === 0) {
    return <p className={styles.empty}>No failures on the default branch in this window.</p>;
  }
  const longest = Math.max(...incidents.map((i) => i.duration_s ?? 0), 1);

  return (
    <ol className={styles.list}>
      {incidents.slice(0, SHOWN).map((incident) => {
        const open = incident.recovered_at === null;
        const duration = open
          ? (now - Date.parse(incident.failed_at)) / 1000
          : (incident.duration_s ?? 0);
        return (
          <li key={incident.failed_at} className={styles.item}>
            <span className={`${styles.when} mono`}>{formatTimestamp(incident.failed_at)}</span>
            <span className={styles.track} aria-hidden>
              <span
                className={`${styles.fill} ${open ? styles.open : ""}`}
                style={{ width: `${Math.min(100, Math.max(3, (duration / longest) * 100))}%` }}
              />
            </span>
            <span className={`${styles.duration} mono ${open ? styles.openText : ""}`}>
              {open ? `ongoing · ${formatDuration(duration)}` : formatDuration(duration)}
            </span>
          </li>
        );
      })}
      {incidents.length > SHOWN && (
        <li className={styles.more}>+{incidents.length - SHOWN} earlier</li>
      )}
    </ol>
  );
}
