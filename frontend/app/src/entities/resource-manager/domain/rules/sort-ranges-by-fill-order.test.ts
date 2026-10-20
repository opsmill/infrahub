import { describe, expect, it } from "vitest";

import { generateNumberPoolRange } from "../../../../../tests/fake/number-pool";
import { sortRangesByFillOrder } from "./sort-ranges-by-fill-order";

describe("sortRangesByFillOrder", () => {
  it("lists the highest weight first", () => {
    // GIVEN
    const low = generateNumberPoolRange({
      id: "low",
      start: { value: 1 },
      end: { value: 50 },
      allocation_weight: { value: 0 },
    });
    const high = generateNumberPoolRange({
      id: "high",
      start: { value: 51 },
      end: { value: 100 },
      allocation_weight: { value: 10 },
    });

    // WHEN
    const sorted = sortRangesByFillOrder([low, high]);

    // THEN
    expect(sorted.map(({ id }) => id)).toEqual(["high", "low"]);
  });

  it("lists the lowest start first when weights are equal", () => {
    // GIVEN
    const later = generateNumberPoolRange({
      id: "later",
      start: { value: 51 },
      end: { value: 100 },
      allocation_weight: { value: 5 },
    });
    const earlier = generateNumberPoolRange({
      id: "earlier",
      start: { value: 1 },
      end: { value: 50 },
      allocation_weight: { value: 5 },
    });

    // WHEN
    const sorted = sortRangesByFillOrder([later, earlier]);

    // THEN
    expect(sorted.map(({ id }) => id)).toEqual(["earlier", "later"]);
  });

  it("lists the lowest end first when weight and start are equal", () => {
    // GIVEN
    const wide = generateNumberPoolRange({
      id: "wide",
      start: { value: 1 },
      end: { value: 100 },
      allocation_weight: { value: 5 },
    });
    const narrow = generateNumberPoolRange({
      id: "narrow",
      start: { value: 1 },
      end: { value: 50 },
      allocation_weight: { value: 5 },
    });

    // WHEN
    const sorted = sortRangesByFillOrder([wide, narrow]);

    // THEN
    expect(sorted.map(({ id }) => id)).toEqual(["narrow", "wide"]);
  });

  it("leaves the given list in its order", () => {
    // GIVEN
    const ranges = [
      generateNumberPoolRange({ id: "low", allocation_weight: { value: 0 } }),
      generateNumberPoolRange({ id: "high", allocation_weight: { value: 10 } }),
    ];

    // WHEN
    sortRangesByFillOrder(ranges);

    // THEN
    expect(ranges.map(({ id }) => id)).toEqual(["low", "high"]);
  });
});
