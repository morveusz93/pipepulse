import Link from "next/link";
import { Suspense } from "react";
import { apiGet } from "@/lib/api";
import type { AuthState } from "@/lib/types";
import { ThemeToggle } from "./ThemeToggle";
import styles from "./Header.module.css";

export function Header() {
  return (
    <header className={styles.header}>
      <div className={styles.inner}>
        <Link href="/" className={styles.brand} aria-label="pipepulse home">
          <Logo />
          <span>pipepulse</span>
        </Link>
        <div className={styles.actions}>
          <Suspense fallback={null}>
            <ModeBadge />
          </Suspense>
          <ThemeToggle />
        </div>
      </div>
    </header>
  );
}

async function ModeBadge() {
  const auth = await apiGet<AuthState>("/api/auth/me").catch(() => null);
  if (!auth?.demo_mode) return null;
  return (
    <span className={styles.badge} title="Generated sample data, no GitLab token involved">
      Demo data
    </span>
  );
}

function Logo() {
  return (
    <svg width="22" height="16" viewBox="0 0 22 16" aria-hidden className={styles.logo}>
      <path
        d="M1 8h5l2-5 3 10 2.5-7L15 8h6"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
