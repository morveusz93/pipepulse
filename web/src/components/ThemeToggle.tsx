"use client";

import styles from "./Header.module.css";

export const THEME_KEY = "pipepulse-theme";

/**
 * Runs before first paint (inlined in <head>) so the stored theme never flashes.
 * `?theme=light|dark` wins over the stored choice (handy for links and screenshots).
 */
export const themeInitScript = `(function(){try{var q=new URLSearchParams(location.search).get("theme");var t=q||localStorage.getItem("${THEME_KEY}");if(t==="light"||t==="dark")document.documentElement.dataset.theme=t}catch(e){}})()`;

export function ThemeToggle() {
  function toggle() {
    const root = document.documentElement;
    const next = root.dataset.theme === "light" ? "dark" : "light";
    root.dataset.theme = next;
    try {
      localStorage.setItem(THEME_KEY, next);
    } catch {
      // Private mode: theme just won't persist.
    }
  }

  // Both icons render; CSS shows the right one from [data-theme], so server and client agree.
  return (
    <button type="button" className={styles.iconButton} onClick={toggle} aria-label="Toggle theme">
      <svg className={styles.sun} width="16" height="16" viewBox="0 0 16 16" aria-hidden>
        <circle cx="8" cy="8" r="3" fill="none" stroke="currentColor" strokeWidth="1.5" />
        <path
          d="M8 1v1.5M8 13.5V15M1 8h1.5M13.5 8H15M3 3l1 1M12 12l1 1M3 13l1-1M12 4l1-1"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
        />
      </svg>
      <svg className={styles.moon} width="16" height="16" viewBox="0 0 16 16" aria-hidden>
        <path
          d="M13.5 9.5A5.5 5.5 0 0 1 6.5 2.5a5.5 5.5 0 1 0 7 7Z"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinejoin="round"
        />
      </svg>
    </button>
  );
}
