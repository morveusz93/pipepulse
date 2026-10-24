"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  type TooltipContentProps,
  type TooltipValueType,
} from "recharts";
import type { TrendPoint } from "@/lib/types";
import { formatDuration, formatPercent } from "@/lib/format";
import styles from "./TrendCharts.module.css";

type ChartTooltipProps = TooltipContentProps<TooltipValueType, string | number>;

const AXIS = { fontSize: 11, fill: "var(--text-faint)", fontFamily: "var(--font-mono)" };

function dayLabel(day: string): string {
  return new Date(`${day}T00:00:00Z`).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    timeZone: "UTC",
  });
}

const NICE_STEPS = [30, 60, 120, 300, 600, 900, 1800, 3600, 7200];

/** Y ticks on round durations (1m, 2m, 5m…) instead of whatever 1/4 of the max happens to be. */
function durationTicks(points: TrendPoint[]): number[] {
  const max = Math.max(60, ...points.map((p) => p.p90_duration_s ?? p.avg_duration_s ?? 0));
  const step = NICE_STEPS.find((s) => max / s <= 5) ?? 7200;
  return Array.from({ length: Math.ceil(max / step) + 1 }, (_, i) => i * step);
}

function minutesTick(seconds: number): string {
  if (seconds >= 3600) return `${+(seconds / 3600).toFixed(1)}h`;
  return seconds % 60 === 0 ? `${seconds / 60}m` : `${+(seconds / 60).toFixed(1)}m`;
}

export function TrendCharts({ points }: { points: TrendPoint[] }) {
  const tickGap = points.length > 14 ? Math.ceil(points.length / 7) - 1 : 0;

  return (
    <div className={styles.grid}>
      <figure className={styles.card}>
        <figcaption className={styles.caption}>
          <span>Duration</span>
          <span className={styles.legend}>
            <i className={styles.keyLine} /> avg <i className={styles.keyDashed} /> p90
          </span>
        </figcaption>
        <div className={styles.chart}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={points} margin={{ top: 8, right: 8, bottom: 0, left: -8 }}>
              <CartesianGrid vertical={false} stroke="var(--chart-grid)" />
              <XAxis
                dataKey="day"
                tickFormatter={dayLabel}
                tick={AXIS}
                tickLine={false}
                axisLine={false}
                interval={tickGap}
              />
              <YAxis
                ticks={durationTicks(points)}
                domain={[0, "dataMax"]}
                tickFormatter={minutesTick}
                tick={AXIS}
                tickLine={false}
                axisLine={false}
                width={44}
              />
              <Tooltip content={DurationTooltip} cursor={{ stroke: "var(--border)" }} />
              <Line
                dataKey="p90_duration_s"
                stroke="var(--chart-line-faint)"
                strokeDasharray="3 3"
                strokeWidth={1.5}
                dot={false}
                connectNulls
                isAnimationActive={false}
              />
              <Line
                dataKey="avg_duration_s"
                stroke="var(--chart-line)"
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 3, strokeWidth: 0, fill: "var(--chart-line)" }}
                connectNulls
                isAnimationActive={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </figure>

      <figure className={styles.card}>
        <figcaption className={styles.caption}>
          <span>Runs per day</span>
          <span className={styles.legend}>
            <i className={styles.keySuccess} /> passed <i className={styles.keyFailure} /> failed
          </span>
        </figcaption>
        <div className={styles.chart}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={points} margin={{ top: 8, right: 8, bottom: 0, left: -8 }}>
              <CartesianGrid vertical={false} stroke="var(--chart-grid)" />
              <XAxis
                dataKey="day"
                tickFormatter={dayLabel}
                tick={AXIS}
                tickLine={false}
                axisLine={false}
                interval={tickGap}
              />
              <YAxis
                allowDecimals={false}
                tick={AXIS}
                tickLine={false}
                axisLine={false}
                width={44}
              />
              <Tooltip content={RunsTooltip} cursor={{ fill: "var(--surface-hover)" }} />
              <Bar dataKey="succeeded" stackId="runs" fill="var(--success)" isAnimationActive={false} />
              <Bar
                dataKey="failed"
                stackId="runs"
                fill="var(--failure)"
                radius={[2, 2, 0, 0]}
                isAnimationActive={false}
              />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </figure>
    </div>
  );
}

function DurationTooltip({ active, payload }: ChartTooltipProps) {
  const point = payload?.[0]?.payload as TrendPoint | undefined;
  if (!active || !point) return null;
  return (
    <div className={styles.tooltip}>
      <div className={styles.tooltipTitle}>{dayLabel(point.day)}</div>
      <Row label="avg" value={formatDuration(point.avg_duration_s)} />
      <Row label="p90" value={formatDuration(point.p90_duration_s)} />
    </div>
  );
}

function RunsTooltip({ active, payload }: ChartTooltipProps) {
  const point = payload?.[0]?.payload as TrendPoint | undefined;
  if (!active || !point) return null;
  return (
    <div className={styles.tooltip}>
      <div className={styles.tooltipTitle}>{dayLabel(point.day)}</div>
      <Row label="passed" value={String(point.succeeded)} />
      <Row label="failed" value={String(point.failed)} />
      <Row label="success" value={formatPercent(point.success_rate)} />
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className={styles.tooltipRow}>
      <span>{label}</span>
      <span className="mono">{value}</span>
    </div>
  );
}
