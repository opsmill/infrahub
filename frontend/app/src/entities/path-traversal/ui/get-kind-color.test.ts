import { describe, expect, test } from "vitest";

import { getKindColor } from "./get-kind-color";

describe("getKindColor", () => {
  test("returns a string", () => {
    const result = getKindColor("InfraDevice");
    expect(typeof result).toBe("string");
  });

  test("returns consistent color for the same kind", () => {
    const color1 = getKindColor("InfraDevice");
    const color2 = getKindColor("InfraDevice");
    expect(color1).toBe(color2);
  });

  test("returns different colors for different kinds", () => {
    const colorA = getKindColor("InfraDevice");
    const colorB = getKindColor("InfraInterface");
    // They could theoretically collide, but these specific strings should not
    expect(colorA).not.toBe(colorB);
  });

  test("returns a valid hex color", () => {
    const result = getKindColor("SomeRandomKind");
    expect(result).toMatch(/^#[0-9a-f]{6}$/);
  });

  test("handles empty string", () => {
    const result = getKindColor("");
    expect(typeof result).toBe("string");
    expect(result).toMatch(/^#[0-9a-f]{6}$/);
  });
});
