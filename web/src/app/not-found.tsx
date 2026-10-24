import Link from "next/link";
import styles from "./page.module.css";

export default function NotFound() {
  return (
    <main className={styles.main}>
      <h1 className={styles.title}>Not found</h1>
      <p className={styles.caption}>This project or page doesn&apos;t exist (anymore).</p>
      <p>
        <Link href="/" className={styles.link}>
          ← Back to all projects
        </Link>
      </p>
    </main>
  );
}
