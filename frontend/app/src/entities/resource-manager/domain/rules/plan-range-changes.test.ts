import { describe, expect, it } from "vitest";

import type {
  RangeRow,
  StoredRange,
} from "@/entities/resource-manager/domain/model/number-pool-range";

import {
  diffRanges,
  hasRangeChanges,
  matchRowsToStored,
  sortStoredRanges,
  toRangeRows,
} from "./plan-range-changes";

const stored = (
  id: string,
  start: number,
  end: number,
  weight: number | null = null
): StoredRange => ({
  id,
  start,
  end,
  weight,
});

const row = (start: string, end: string, weight = "", rangeId?: string): RangeRow => ({
  ...(rangeId ? { rangeId } : {}),
  start,
  end,
  weight,
});

describe("sortStoredRanges", () => {
  it("sorts by weight descending with an empty weight as 0, then by start", () => {
    // GIVEN
    const ranges = [
      stored("a", 50, 60),
      stored("b", 30, 40, 1),
      stored("c", 10, 20, 5),
      stored("d", 1, 5, 1),
      stored("e", 0, 0),
      stored("f", 100, 110, 0),
    ];

    // WHEN
    const sorted = sortStoredRanges(ranges);

    // THEN
    expect(sorted.map((range) => range.id)).toEqual(["c", "d", "b", "e", "a", "f"]);
  });

  it("orders an empty weight and a weight of 0 by start", () => {
    // GIVEN
    const ranges = [stored("zero", 100, 200, 0), stored("empty", 1, 10, null)];

    // WHEN
    const sorted = sortStoredRanges(ranges);

    // THEN
    expect(sorted.map((range) => range.id)).toEqual(["empty", "zero"]);
  });

  it("does not change the given list", () => {
    // GIVEN
    const ranges = [stored("a", 20, 30), stored("b", 1, 10)];

    // WHEN
    sortStoredRanges(ranges);

    // THEN
    expect(ranges.map((range) => range.id)).toEqual(["a", "b"]);
  });
});

describe("diffRanges", () => {
  it("returns no changes for unchanged rows", () => {
    // GIVEN
    const ranges = [stored("a", 1, 10, 5), stored("b", 11, 20)];
    const rows = [row("1", "10", "5", "a"), row(" 11 ", "20", "", "b")];

    // WHEN
    const changes = diffRanges(ranges, rows);

    // THEN
    expect(changes).toEqual({ deletes: [], smaller: [], larger: [], creates: [] });
  });

  it("deletes stored ranges that are no longer on a row", () => {
    // GIVEN
    const ranges = [stored("a", 1, 10), stored("b", 11, 20)];
    const rows = [row("1", "10", "", "a")];

    // WHEN
    const changes = diffRanges(ranges, rows);

    // THEN
    expect(changes).toEqual({ deletes: ["b"], smaller: [], larger: [], creates: [] });
  });

  it("creates rows without a stored range, with an empty weight as null", () => {
    // GIVEN
    const rows = [row("1", "10"), row("20", "30", "3")];

    // WHEN
    const changes = diffRanges([], rows);

    // THEN
    expect(changes).toEqual({
      deletes: [],
      smaller: [],
      larger: [],
      creates: [
        { start: 1, end: 10, weight: null },
        { start: 20, end: 30, weight: 3 },
      ],
    });
  });

  it("treats a weight-only change as smaller", () => {
    // GIVEN
    const ranges = [stored("a", 1, 10, 5)];
    const rows = [row("1", "10", "", "a")];

    // WHEN
    const changes = diffRanges(ranges, rows);

    // THEN
    expect(changes).toEqual({
      deletes: [],
      smaller: [{ id: "a", start: 1, end: 10, weight: null }],
      larger: [],
      creates: [],
    });
  });

  it("splits 1–10 and 11–20 becoming 1–15 and 16–20 into larger and smaller", () => {
    // GIVEN
    const ranges = [stored("a", 1, 10), stored("b", 11, 20)];
    const rows = [row("1", "15", "", "a"), row("16", "20", "", "b")];

    // WHEN
    const changes = diffRanges(ranges, rows);

    // THEN
    expect(changes).toEqual({
      deletes: [],
      smaller: [{ id: "b", start: 16, end: 20, weight: null }],
      larger: [{ id: "a", start: 1, end: 15, weight: null }],
      creates: [],
    });
  });

  it("treats a range moved outside its old bounds as larger", () => {
    // GIVEN
    const ranges = [stored("a", 10, 20, 2)];
    const rows = [row("5", "15", "2", "a")];

    // WHEN
    const changes = diffRanges(ranges, rows);

    // THEN
    expect(changes.larger).toEqual([{ id: "a", start: 5, end: 15, weight: 2 }]);
  });

  it("sends a larger update after the larger update that frees its new bounds", () => {
    // GIVEN
    const ranges = [stored("a", 1, 10), stored("b", 11, 20)];
    const rows = [row("11", "20", "", "a"), row("21", "30", "", "b")];

    // WHEN
    const changes = diffRanges(ranges, rows);

    // THEN
    expect(changes.larger).toEqual([
      { id: "b", start: 21, end: 30, weight: null },
      { id: "a", start: 11, end: 20, weight: null },
    ]);
  });

  it("keeps the row order of larger updates that free each other's bounds", () => {
    // GIVEN
    const ranges = [stored("a", 1, 10), stored("b", 11, 20)];
    const rows = [row("11", "20", "", "a"), row("1", "10", "", "b")];

    // WHEN
    const changes = diffRanges(ranges, rows);

    // THEN
    expect(changes.larger.map((update) => update.id)).toEqual(["a", "b"]);
  });

  it("creates a row whose stored range no longer exists", () => {
    // GIVEN
    const rows = [row("1", "10", "", "gone")];

    // WHEN
    const changes = diffRanges([], rows);

    // THEN
    expect(changes.creates).toEqual([{ start: 1, end: 10, weight: null }]);
  });

  it("groups deletes, smaller, larger and creates together", () => {
    // GIVEN
    const ranges = [stored("a", 1, 100), stored("b", 200, 300), stored("c", 400, 500)];
    const rows = [row("10", "90", "", "a"), row("150", "300", "", "b"), row("600", "700")];

    // WHEN
    const changes = diffRanges(ranges, rows);

    // THEN
    expect(changes).toEqual({
      deletes: ["c"],
      smaller: [{ id: "a", start: 10, end: 90, weight: null }],
      larger: [{ id: "b", start: 150, end: 300, weight: null }],
      creates: [{ start: 600, end: 700, weight: null }],
    });
  });
});

describe("matchRowsToStored", () => {
  it("links unlinked rows to stored ranges with equal bounds", () => {
    // GIVEN
    const ranges = [stored("a", 1, 10, 4)];
    const rows = [row("1", "10", "7")];

    // WHEN
    const matched = matchRowsToStored(rows, ranges);

    // THEN
    expect(matched).toEqual([row("1", "10", "7", "a")]);
  });

  it("does not link a stored range that is already linked", () => {
    // GIVEN
    const ranges = [stored("a", 1, 10)];
    const rows = [row("1", "10", "", "a"), row("1", "10")];

    // WHEN
    const matched = matchRowsToStored(rows, ranges);

    // THEN
    expect(matched).toEqual([row("1", "10", "", "a"), row("1", "10")]);
  });

  it("links a stored range to only one unlinked row", () => {
    // GIVEN
    const ranges = [stored("a", 1, 10)];
    const rows = [row("1", "10"), row("1", "10")];

    // WHEN
    const matched = matchRowsToStored(rows, ranges);

    // THEN
    expect(matched).toEqual([row("1", "10", "", "a"), row("1", "10")]);
  });

  it("leaves rows without a matching stored range as typed", () => {
    // GIVEN
    const ranges = [stored("a", 1, 10)];
    const rows = [row("1", "11"), row("abc", "")];

    // WHEN
    const matched = matchRowsToStored(rows, ranges);

    // THEN
    expect(matched).toEqual(rows);
  });
});

describe("toRangeRows", () => {
  it("lists stored ranges as linked rows of typed strings, by weight then start", () => {
    // GIVEN
    const ranges = [stored("a", 300, 399), stored("b", 100, 199, 10)];

    // WHEN
    const rows = toRangeRows(ranges);

    // THEN
    expect(rows).toEqual([row("100", "199", "10", "b"), row("300", "399", "", "a")]);
  });
});

describe("hasRangeChanges", () => {
  it("is false when no group has a change", () => {
    // GIVEN
    const changes = diffRanges([stored("a", 1, 10)], [row("1", "10", "", "a")]);

    // WHEN
    const result = hasRangeChanges(changes);

    // THEN
    expect(result).toBe(false);
  });

  it("is true when one group has a change", () => {
    // GIVEN
    const changes = diffRanges([stored("a", 1, 10)], []);

    // WHEN
    const result = hasRangeChanges(changes);

    // THEN
    expect(result).toBe(true);
  });
});
