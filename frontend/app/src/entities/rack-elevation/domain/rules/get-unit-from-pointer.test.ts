import { describe, expect, it } from "vitest";

import { getUnitFromPointer } from "./get-unit-from-pointer";

const DRAWING = { top: 32, unitHeight: 24, rackHeight: 12 };

describe("getUnitFromPointer", () => {
  it("returns the top unit for a pointer on the first row", () => {
    expect(getUnitFromPointer({ ...DRAWING, y: 40 })).toBe(12);
  });

  it("returns unit 1 for a pointer on the last row", () => {
    expect(getUnitFromPointer({ ...DRAWING, y: 32 + 11 * 24 + 5 })).toBe(1);
  });

  it("changes unit exactly on a row boundary", () => {
    expect(getUnitFromPointer({ ...DRAWING, y: 32 + 24 - 0.5 })).toBe(12);
    expect(getUnitFromPointer({ ...DRAWING, y: 32 + 24 })).toBe(11);
  });

  it("returns null above the rack", () => {
    expect(getUnitFromPointer({ ...DRAWING, y: 10 })).toBeNull();
  });

  it("returns null below the rack", () => {
    expect(getUnitFromPointer({ ...DRAWING, y: 32 + 12 * 24 })).toBeNull();
  });
});
