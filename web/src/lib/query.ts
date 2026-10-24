/** Page search params as Next.js hands them over. */
export type SearchParams = Record<string, string | string[] | undefined>;

export function first(params: SearchParams, key: string): string | undefined {
  const value = params[key];
  return Array.isArray(value) ? value[0] : value;
}

/** First value of `key` if it's one of `allowed`, else `fallback`. */
export function pick<T extends string>(
  params: SearchParams,
  key: string,
  allowed: readonly T[],
  fallback: T,
): T {
  const value = first(params, key);
  return allowed.includes(value as T) ? (value as T) : fallback;
}

/**
 * Relative href that keeps the current params and applies `changes`. A change to `null`
 * removes the key; keys are sorted so equal states produce equal URLs.
 */
export function hrefWith(params: SearchParams, changes: Record<string, string | null>): string {
  const merged: Record<string, string> = {};
  for (const [key, value] of Object.entries(params)) {
    const v = Array.isArray(value) ? value[0] : value;
    if (v !== undefined) merged[key] = v;
  }
  for (const [key, value] of Object.entries(changes)) {
    if (value === null) delete merged[key];
    else merged[key] = value;
  }
  const query = new URLSearchParams(Object.entries(merged).sort(([a], [b]) => a.localeCompare(b)));
  const qs = query.toString();
  return qs ? `?${qs}` : "?";
}
