import { describe, expect, it } from "vitest";

import { resolvePriority } from "@/shared/api/priority";

describe("resolvePriority", () => {
  it("maps exactly 'low' to 'low'", () => {
    expect(resolvePriority("low")).toBe("low");
  });

  it("maps 'high' to 'high'", () => {
    expect(resolvePriority("high")).toBe("high");
  });

  it("maps the backend fallback 'medium' to 'high'", () => {
    expect(resolvePriority("medium")).toBe("high");
  });

  it("maps undefined (absent context) to 'high'", () => {
    expect(resolvePriority(undefined)).toBe("high");
  });

  it("maps a non-string runtime value to 'high'", () => {
    expect(resolvePriority(123)).toBe("high");
  });
});
