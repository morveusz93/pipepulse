"use client";

import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import styles from "./DeleteProjectButton.module.css";

/**
 * Deletes a project that was removed from PIPEPULSE_PROJECTS, with all its history, after the
 * user types its path. The API refuses projects that are still tracked.
 */
export function DeleteProjectButton({
  projectId,
  path,
  afterDelete = "refresh",
}: {
  projectId: number;
  path: string;
  /** "refresh" re-renders the current page; "home" goes back to the dashboard. */
  afterDelete?: "refresh" | "home";
}) {
  const router = useRouter();
  const dialog = useRef<HTMLDialogElement>(null);
  const [typed, setTyped] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function open() {
    setTyped("");
    setError(null);
    dialog.current?.showModal();
  }

  async function confirm(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const response = await fetch(`/api/projects/${projectId}`, {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ confirm: typed }),
      });
      if (!response.ok && response.status !== 404) {
        const body = (await response.json().catch(() => null)) as { detail?: string } | null;
        throw new Error(body?.detail ?? `Delete failed (${response.status})`);
      }
      dialog.current?.close();
      // A full navigation: router.push would show the dashboard from the client cache, still
      // listing this project; replace() also keeps "back" from returning to a deleted page.
      if (afterDelete === "home") window.location.replace("/");
      else router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <button type="button" className={styles.trigger} onClick={open}>
        Delete history…
      </button>
      <dialog ref={dialog} className={styles.dialog} aria-labelledby={`delete-title-${projectId}`}>
        <form onSubmit={confirm} className={styles.form}>
          <h2 id={`delete-title-${projectId}`} className={styles.title}>
            Delete {path}?
          </h2>
          <p className={styles.text}>
            This permanently deletes the project and its whole pipeline history from pipepulse.
            Nothing changes in GitLab.
          </p>
          <label className={styles.label}>
            <span>
              Type <code>{path}</code> to confirm
            </span>
            <input
              className={styles.input}
              value={typed}
              onChange={(event) => setTyped(event.target.value)}
              autoComplete="off"
              spellCheck={false}
              autoFocus
            />
          </label>
          {error && (
            <p className={styles.error} role="alert">
              {error}
            </p>
          )}
          <div className={styles.actions}>
            <button type="button" className={styles.cancel} onClick={() => dialog.current?.close()}>
              Cancel
            </button>
            <button
              type="submit"
              className={styles.danger}
              disabled={busy || typed.trim() !== path}
            >
              {busy ? "Deleting…" : "Delete project and history"}
            </button>
          </div>
        </form>
      </dialog>
    </>
  );
}
