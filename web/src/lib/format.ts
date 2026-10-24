/** 3m 48s · 1h 02m · 42s */
export function formatDuration(seconds: number | null | undefined): string {
  if (seconds == null) return "—";
  const s = Math.round(seconds);
  if (s < 60) return `${s}s`;
  const minutes = Math.floor(s / 60);
  if (minutes < 60) return `${minutes}m ${String(s % 60).padStart(2, "0")}s`;
  const hours = Math.floor(minutes / 60);
  return `${hours}h ${String(minutes % 60).padStart(2, "0")}m`;
}

/** just now · 12m ago · 3h ago · 2d ago */
export function formatRelative(iso: string, now: number = Date.now()): string {
  const seconds = Math.max(0, (now - new Date(iso).getTime()) / 1000);
  if (seconds < 45) return "just now";
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 36) return `${hours}h ago`;
  return `${Math.round(hours / 24)}d ago`;
}

export function formatPercent(rate: number | null | undefined, digits = 1): string {
  if (rate == null) return "—";
  return `${(rate * 100).toFixed(digits)}%`;
}

export function formatTimestamp(iso: string): string {
  return new Date(iso).toLocaleString("en-GB", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "UTC",
  });
}

export const ACTIVE_STATUSES = new Set([
  "running",
  "pending",
  "created",
  "preparing",
  "waiting_for_resource",
]);

export type StatusTone = "success" | "failure" | "running" | "neutral";

export function statusTone(status: string): StatusTone {
  if (status === "success") return "success";
  if (status === "failed") return "failure";
  if (ACTIVE_STATUSES.has(status)) return "running";
  return "neutral";
}
