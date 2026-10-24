import { parseAnsi } from "@/lib/ansi";
import styles from "./LogViewer.module.css";

/** Terminal-style log tail. Opens scrolled to the bottom, where the error usually is. */
export function LogViewer({ log, label }: { log: string; label: string }) {
  const lines = parseAnsi(log);
  // Drop the trailing empty line most traces end with.
  while (lines.length > 0 && lines.at(-1)!.length === 0) lines.pop();

  return (
    <div className={styles.viewport} tabIndex={0} role="region" aria-label={label}>
      {/* column-reverse keeps the scroll anchored at the bottom without any JS */}
      <div className={styles.scroller}>
        <pre className={styles.log}>
          {lines.map((segments, i) => (
            <span key={i} className={styles.line}>
              {segments.map((segment, j) => (
                <span
                  key={j}
                  className={[
                    segment.color && styles[segment.color],
                    segment.bold && styles.bold,
                  ]
                    .filter(Boolean)
                    .join(" ") || undefined}
                >
                  {segment.text}
                </span>
              ))}
              {"\n"}
            </span>
          ))}
        </pre>
      </div>
    </div>
  );
}
