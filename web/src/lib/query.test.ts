import { describe, expect, it } from "vitest";
import { first, hrefWith, pick } from "./query";

describe("hrefWith", () => {
  it("keeps existing params and applies changes", () => {
    expect(hrefWith({ days: "30", status: "failed" }, { page: "2" })).toBe(
      "?days=30&page=2&status=failed",
    );
  });

  it("removes keys set to null", () => {
    expect(hrefWith({ days: "30", page: "3" }, { page: null })).toBe("?days=30");
  });

  it("returns a bare ? when nothing is left, so the link still clears the query", () => {
    expect(hrefWith({ page: "2" }, { page: null })).toBe("?");
  });

  it("uses the first value of repeated params", () => {
    expect(hrefWith({ status: ["failed", "success"] }, {})).toBe("?status=failed");
  });
});

describe("pick / first", () => {
  it("accepts only allowed values", () => {
    expect(pick({ sort: "-duration" }, "sort", ["-created_at", "-duration"], "-created_at")).toBe(
      "-duration",
    );
    expect(pick({ sort: "drop table" }, "sort", ["-created_at"], "-created_at")).toBe(
      "-created_at",
    );
  });

  it("first handles arrays and missing keys", () => {
    expect(first({ a: ["1", "2"] }, "a")).toBe("1");
    expect(first({}, "a")).toBeUndefined();
  });
});
