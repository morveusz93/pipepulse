"use client";

import styles from "./page.module.css";

export default function Error({ reset }: { error: Error; reset: () => void }) {
  return (
    <main className={styles.main}>
      <h1 className={styles.title}>Can&apos;t reach the pipepulse API</h1>
      <p className={styles.caption}>
        The dashboard couldn&apos;t load pipeline data. Check that the API is running.
      </p>
      <button type="button" onClick={reset}>
        Try again
      </button>
    </main>
  );
}
