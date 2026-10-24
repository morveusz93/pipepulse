/**
 * Minimal ANSI parser for GitLab runner traces.
 *
 * Handles what runners actually emit: SGR colors and bold, erase-line (`ESC[0K`, dropped),
 * GitLab section markers (`section_start:<ts>:<name>[opts]\r`, removed) and carriage-return
 * overwrites (progress bars: only text after the last `\r` on a line survives).
 * Style carries across newlines, like in a terminal.
 */

export type AnsiColor =
  | "black"
  | "red"
  | "green"
  | "yellow"
  | "blue"
  | "magenta"
  | "cyan"
  | "white"
  | "gray";

export interface Segment {
  text: string;
  color?: AnsiColor;
  bold?: boolean;
}

const COLORS: AnsiColor[] = ["black", "red", "green", "yellow", "blue", "magenta", "cyan", "white"];
const SECTION_MARKER = /section_(?:start|end):\d+:[\w.-]+(?:\[[^\]]*\])?\r/g;
const ESCAPE = /\x1b\[([\d;]*)([A-Za-z])/g;

interface Style {
  color?: AnsiColor;
  bold?: boolean;
}

export function parseAnsi(raw: string): Segment[][] {
  const style: Style = {};
  return raw
    .replace(SECTION_MARKER, "")
    .split("\n")
    .map((line) => parseLine(visiblePart(line), style));
}

/** What a terminal would show after carriage returns overwrite the line. */
function visiblePart(line: string): string {
  const trimmed = line.endsWith("\r") ? line.slice(0, -1) : line;
  const lastCr = trimmed.lastIndexOf("\r");
  if (lastCr === -1) return trimmed;
  // Keep escape codes from before the overwrite so the active style is preserved.
  const codes = trimmed.slice(0, lastCr).match(ESCAPE) ?? [];
  return codes.join("") + trimmed.slice(lastCr + 1);
}

function parseLine(line: string, style: Style): Segment[] {
  const segments: Segment[] = [];
  let cursor = 0;
  for (const match of line.matchAll(ESCAPE)) {
    push(segments, line.slice(cursor, match.index), style);
    cursor = match.index + match[0].length;
    if (match[2] === "m") applySgr(match[1], style);
  }
  push(segments, line.slice(cursor), style);
  return segments;
}

function push(segments: Segment[], text: string, style: Style) {
  if (!text) return;
  const last = segments.at(-1);
  if (last && last.color === style.color && last.bold === style.bold) {
    last.text += text;
  } else {
    segments.push({ text, ...(style.color && { color: style.color }), ...(style.bold && { bold: true }) });
  }
}

function applySgr(params: string, style: Style) {
  const codes = params === "" ? [0] : params.split(";").map(Number);
  for (let i = 0; i < codes.length; i++) {
    const code = codes[i];
    if (code === 0) {
      delete style.color;
      delete style.bold;
    } else if (code === 1) {
      style.bold = true;
    } else if (code === 22) {
      delete style.bold;
    } else if (code >= 30 && code <= 37) {
      style.color = COLORS[code - 30];
    } else if (code >= 90 && code <= 97) {
      style.color = code === 90 ? "gray" : COLORS[code - 90];
    } else if (code === 39) {
      delete style.color;
    } else if (code === 38 || code === 48) {
      // Extended colors (38;5;n or 38;2;r;g;b): skip their arguments, keep current color.
      i += codes[i + 1] === 5 ? 2 : codes[i + 1] === 2 ? 4 : 0;
    }
  }
}

const RUNNER_NOISE = /^(ERROR: Job failed|Cleaning up|Uploading artifacts)/;

/**
 * The single most telling line of a failed job's log, for a one-line preview: the first
 * red line that isn't the runner's generic "ERROR: Job failed" footer, else the last
 * non-empty line before it.
 */
export function errorExcerpt(raw: string): string | null {
  const lines = parseAnsi(raw)
    .map((segments) => ({
      text: segments.map((s) => s.text).join("").trim(),
      red: segments.some((s) => s.color === "red" && s.text.trim()),
    }))
    .filter((line) => line.text && !RUNNER_NOISE.test(line.text));
  return (lines.find((line) => line.red) ?? lines.at(-1))?.text ?? null;
}
