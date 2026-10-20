import { describe, expect, it } from "vitest";

import { findOverlappingRanges } from "./find-overlapping-ranges";

describe("findOverlappingRanges", () => {
  it("reports nothing for ranges that only touch end to start", () => {
    // GIVEN
    const ranges = [
      { key: "a", start: 1, end: 10 },
      { key: "b", start: 11, end: 20 },
    ];

    // WHEN
    const overlaps = findOverlappingRanges(ranges);

    // THEN
    expect(overlaps.size).toBe(0);
  });

  it("reports both ranges when they share a number", () => {
    // GIVEN
    const ranges = [
      { key: "a", start: 1, end: 10 },
      { key: "b", start: 10, end: 20 },
    ];

    // WHEN
    const overlaps = findOverlappingRanges(ranges);

    // THEN
    expect(overlaps.get("a")).toEqual([{ start: 10, end: 20 }]);
    expect(overlaps.get("b")).toEqual([{ start: 1, end: 10 }]);
  });

  it("reports every range a range overlaps", () => {
    // GIVEN
    const ranges = [
      { key: "wide", start: 1, end: 100 },
      { key: "low", start: 5, end: 10 },
      { key: "high", start: 90, end: 120 },
    ];

    // WHEN
    const overlaps = findOverlappingRanges(ranges);

    // THEN
    expect(overlaps.get("wide")).toEqual([
      { start: 5, end: 10 },
      { start: 90, end: 120 },
    ]);
    expect(overlaps.get("low")).toEqual([{ start: 1, end: 100 }]);
    expect(overlaps.get("high")).toEqual([{ start: 1, end: 100 }]);
  });

  it("compares ranges entered out of numeric order", () => {
    // GIVEN
    const ranges = [
      { key: "later", start: 40, end: 50 },
      { key: "earlier", start: 1, end: 19 },
      { key: "inside", start: 45, end: 46 },
    ];

    // WHEN
    const overlaps = findOverlappingRanges(ranges);

    // THEN
    expect([...overlaps.keys()].sort()).toEqual(["inside", "later"]);
  });
});
