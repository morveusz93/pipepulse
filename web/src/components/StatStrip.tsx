import styles from "./StatStrip.module.css";

export type StatTone = "failure" | "success" | "running";

/** A row of headline numbers in one bordered strip. */
export function StatStrip({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <section className={styles.strip} aria-label={label}>
      {children}
    </section>
  );
}

export function Stat({
  label,
  value,
  tone,
  children,
}: {
  label: string;
  value: string;
  tone?: StatTone;
  children?: React.ReactNode;
}) {
  return (
    <div className={styles.stat}>
      <div className={styles.label}>{label}</div>
      <div className={`${styles.value} mono ${tone ? styles[tone] : ""}`}>{value}</div>
      {children != null && <div className={styles.sub}>{children}</div>}
    </div>
  );
}

/** Colored sub-line text, e.g. a delta that got worse. */
export function Tone({ tone, children }: { tone?: StatTone; children: React.ReactNode }) {
  return <span className={tone ? styles[tone] : undefined}>{children}</span>;
}
