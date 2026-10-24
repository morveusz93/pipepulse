import { describe, expect, it } from "vitest";
import { errorExcerpt, parseAnsi } from "./ansi";

const text = (lines: ReturnType<typeof parseAnsi>) => lines.map((l) => l.map((s) => s.text).join(""));

describe("parseAnsi", () => {
  it("passes plain text through", () => {
    expect(parseAnsi("hello\nworld")).toEqual([[{ text: "hello" }], [{ text: "world" }]]);
  });

  it("applies colors and bold, and resets", () => {
    const [line] = parseAnsi("\x1b[31;1mERROR\x1b[0;m done");
    expect(line).toEqual([{ text: "ERROR", color: "red", bold: true }, { text: " done" }]);
  });

  it("carries style across newlines like a terminal", () => {
    const lines = parseAnsi("\x1b[32mok\nstill green\x1b[0m\nplain");
    expect(lines[1]).toEqual([{ text: "still green", color: "green" }]);
    expect(lines[2]).toEqual([{ text: "plain" }]);
  });

  it("maps bright black to gray and other bright colors to base colors", () => {
    expect(parseAnsi("\x1b[90ma\x1b[91mb")[0]).toEqual([
      { text: "a", color: "gray" },
      { text: "b", color: "red" },
    ]);
  });

  it("removes GitLab section markers and erase-line codes", () => {
    const raw =
      "section_start:1729760007:step_script[collapsed=true]\r\x1b[0K\x1b[0K\x1b[36;1mExecuting\x1b[0;m\n" +
      "section_end:1729760100:step_script\r\x1b[0K";
    expect(text(parseAnsi(raw))).toEqual(["Executing", ""]);
  });

  it("keeps only what is left after carriage-return overwrites", () => {
    expect(text(parseAnsi("progress 10%\rprogress 55%\rprogress 100%\n"))).toEqual([
      "progress 100%",
      "",
    ]);
  });

  it("keeps the active style through an overwrite", () => {
    expect(parseAnsi("\x1b[33mloading\rdone")[0]).toEqual([{ text: "done", color: "yellow" }]);
  });

  it("strips trailing CR from CRLF lines", () => {
    expect(text(parseAnsi("a\r\nb\r\n"))).toEqual(["a", "b", ""]);
  });

  it("skips extended color arguments", () => {
    expect(parseAnsi("\x1b[38;5;196mx\x1b[38;2;1;2;3my\x1b[1mz")[0]).toEqual([
      { text: "xy" },
      { text: "z", bold: true },
    ]);
  });
});

describe("errorExcerpt", () => {
  it("picks the first red line, skipping the runner footer", () => {
    const log =
      "Running 42 tests\n\x1b[31;1mError: Cannot find module './auth'\x1b[0;m\nRequire stack:\n" +
      "\x1b[31;1mERROR: Job failed: exit code 1\n\x1b[0;m";
    expect(errorExcerpt(log)).toBe("Error: Cannot find module './auth'");
  });

  it("falls back to the last meaningful line", () => {
    expect(errorExcerpt("step 1\nboom happened\n\x1b[31mERROR: Job failed: exit code 2\n")).toBe(
      "boom happened",
    );
  });

  it("handles empty logs", () => {
    expect(errorExcerpt("")).toBeNull();
  });
});
