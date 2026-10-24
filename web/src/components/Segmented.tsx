import Link from "next/link";
import styles from "./Segmented.module.css";

export interface SegmentOption {
  label: string;
  href: string;
  current: boolean;
}

/** A row of mutually exclusive links (state lives in the URL, so it works without JS). */
export function Segmented({ label, options }: { label: string; options: SegmentOption[] }) {
  return (
    <nav className={styles.group} aria-label={label}>
      {options.map((option) => (
        <Link
          key={option.label}
          href={option.href}
          className={styles.option}
          aria-current={option.current ? "true" : undefined}
          scroll={false}
        >
          {option.label}
        </Link>
      ))}
    </nav>
  );
}
