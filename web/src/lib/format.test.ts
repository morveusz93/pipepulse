import { describe, expect, it } from "vitest";
import { formatDuration, formatPercent, formatRelative, refLabel, statusTone } from "./format";

describe("formatDuration", () => {
  it.each([
    [null, "—"],
    [42, "42s"],
    [228, "3m 48s"],
    [3725, "1h 02m"],
  ])("%s -> %s", (seconds, expected) => {
    expect(formatDuration(seconds)).toBe(expected);
  });
});

describe("formatRelative", () => {
  const now = Date.parse("2026-10-24T12:00:00Z");
  it.each([
    ["2026-10-24T11:59:40Z", "just now"],
    ["2026-10-24T11:48:00Z", "12m ago"],
    ["2026-10-24T09:00:00Z", "3h ago"],
    ["2026-10-21T12:00:00Z", "3d ago"],
  ])("%s -> %s", (iso, expected) => {
    expect(formatRelative(iso, now)).toBe(expected);
  });
});

it("formatPercent", () => {
  expect(formatPercent(0.9076)).toBe("90.8%");
  expect(formatPercent(null)).toBe("—");
});

it("statusTone", () => {
  expect(statusTone("success")).toBe("success");
  expect(statusTone("failed")).toBe("failure");
  expect(statusTone("waiting_for_resource")).toBe("running");
  expect(statusTone("canceled")).toBe("neutral");
});

it("refLabel shortens merge request refs", () => {
  expect(refLabel("refs/merge-requests/137/head")).toBe("!137");
  expect(refLabel("feat/dark-mode")).toBe("feat/dark-mode");
});
