import { describe, expect, test } from "vitest";

import { HIDDEN_NAMESPACES } from "./visible-namespace";

describe("HIDDEN_NAMESPACES", () => {
  test("is a Set", () => {
    expect(HIDDEN_NAMESPACES).toBeInstanceOf(Set);
  });

  test("contains expected namespaces", () => {
    const expected = ["Core", "Internal", "Builtin", "Lineage", "Profile", "Template"];
    for (const ns of expected) {
      expect(HIDDEN_NAMESPACES.has(ns)).toBe(true);
    }
  });

  test("has exactly 6 entries", () => {
    expect(HIDDEN_NAMESPACES.size).toBe(6);
  });

  test("does not contain user namespaces", () => {
    expect(HIDDEN_NAMESPACES.has("Infra")).toBe(false);
    expect(HIDDEN_NAMESPACES.has("Custom")).toBe(false);
  });
});
