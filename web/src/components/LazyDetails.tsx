"use client";

import { useState } from "react";

/**
 * Native <details>, but the body is only mounted after the first open. Keeps expensive or
 * fetching children (job logs) from loading for rows nobody expands.
 */
export function LazyDetails({
  summary,
  className,
  summaryClassName,
  children,
}: {
  summary: React.ReactNode;
  className?: string;
  summaryClassName?: string;
  children: React.ReactNode;
}) {
  const [opened, setOpened] = useState(false);
  return (
    <details
      className={className}
      onToggle={(event) => {
        if (event.currentTarget.open) setOpened(true);
      }}
    >
      <summary className={summaryClassName}>{summary}</summary>
      {opened && children}
    </details>
  );
}
