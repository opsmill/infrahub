import { describe, expect, it } from "vitest";

import { DEFAULT_PRIORITY, PRIORITY_HEADER, resolvePriority } from "@/shared/api/priority";

describe("resolvePriority", () => {
  it("maps exactly 'low' to 'low'", () => {
    expect(resolvePriority("low")).toBe("low");
  });

  it("maps 'high' to 'high'", () => {
    expect(resolvePriority("high")).toBe("high");
  });

  it("maps the backend fallback 'normal' to 'high'", () => {
    expect(resolvePriority("normal")).toBe("high");
  });

  it("maps undefined to 'high'", () => {
    expect(resolvePriority(undefined)).toBe("high");
  });

  it("maps an arbitrary string to 'high'", () => {
    expect(resolvePriority("garbage")).toBe("high");
  });

  it("maps a non-string value to 'high'", () => {
    expect(resolvePriority(123)).toBe("high");
  });
});

describe("priority contract constants", () => {
  it("uses the title-cased 'X-Priority' header name", () => {
    expect(PRIORITY_HEADER).toBe("X-Priority");
  });

  it("defaults to 'high'", () => {
    expect(DEFAULT_PRIORITY).toBe("high");
  });
});
