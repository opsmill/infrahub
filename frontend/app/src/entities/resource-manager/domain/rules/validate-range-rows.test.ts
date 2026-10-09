import { describe, expect, it } from "vitest";

import type { RangeRow } from "@/entities/resource-manager/domain/model/number-pool-range";

import { getRangeClipHint, validateRangeRows } from "./validate-range-rows";

const row = (start: string, end: string, weight = ""): RangeRow => ({ start, end, weight });

describe("validateRangeRows", () => {
  it("returns no errors for valid, non-overlapping rows", () => {
    // GIVEN
    const rows = [row("1", "10", "5"), row("11", "20"), row("-20", "-11", "0")];

    // WHEN
    const errors = validateRangeRows(rows);

    // THEN
    expect(errors).toEqual({});
  });

  it("requires start and end", () => {
    // GIVEN
    const rows = [row("", "  ")];

    // WHEN
    const errors = validateRangeRows(rows);

    // THEN
    expect(errors).toEqual({ 0: { start: "Required", end: "Required" } });
  });

  it.each(["1e3", "1.0", "abc", "1 000"])("rejects %s as a bound", (value) => {
    // GIVEN
    const rows = [row(value, value)];

    // WHEN
    const errors = validateRangeRows(rows);

    // THEN
    expect(errors).toEqual({ 0: { start: "Whole number", end: "Whole number" } });
  });

  it("accepts a bound above 2^53", () => {
    // GIVEN
    const rows = [row("1", "9223372036854775807")];

    // WHEN
    const errors = validateRangeRows(rows);

    // THEN
    expect(errors).toEqual({});
  });

  it("compares bounds above 2^53 exactly", () => {
    // GIVEN two ranges that a JavaScript number would round to the same value
    const rows = [
      row("9007199254740992", "9007199254740992"),
      row("9007199254740993", "9007199254740993"),
      row("9223372036854775806", "9223372036854775807"),
      row("9223372036854775807", "9223372036854775807"),
    ];

    // WHEN
    const errors = validateRangeRows(rows);

    // THEN only the ranges that share a number overlap, and the bound is shown exactly
    expect(errors).toEqual({
      2: { row: "Overlaps 9,223,372,036,854,775,807 – 9,223,372,036,854,775,807" },
      3: { row: "Overlaps 9,223,372,036,854,775,806 – 9,223,372,036,854,775,807" },
    });
  });

  it("accepts negative bounds and surrounding spaces", () => {
    // GIVEN
    const rows = [row(" -5 ", "-1")];

    // WHEN
    const errors = validateRangeRows(rows);

    // THEN
    expect(errors).toEqual({});
  });

  it("reports an end lower than its start on the end", () => {
    // GIVEN
    const rows = [row("10", "5")];

    // WHEN
    const errors = validateRangeRows(rows);

    // THEN
    expect(errors).toEqual({ 0: { end: "Must not be lower than start" } });
  });

  it.each(["-1", "1.5", "x", "9007199254740993"])("rejects %s as a weight", (weight) => {
    // GIVEN
    const rows = [row("1", "10", weight)];

    // WHEN
    const errors = validateRangeRows(rows);

    // THEN
    expect(errors).toEqual({ 0: { weight: "Whole number of 0 or more" } });
  });

  it("names the other range on both overlapping rows, with thousands separators", () => {
    // GIVEN
    const rows = [row("1", "1500"), row("2000", "3000"), row("1000", "2500")];

    // WHEN
    const errors = validateRangeRows(rows);

    // THEN
    expect(errors).toEqual({
      0: { row: "Overlaps 1,000 – 2,500" },
      1: { row: "Overlaps 1,000 – 2,500" },
      2: { row: "Overlaps 2,000 – 3,000" },
    });
  });

  it("reports rows with identical bounds as overlapping", () => {
    // GIVEN
    const rows = [row("1", "10"), row("1", "10")];

    // WHEN
    const errors = validateRangeRows(rows);

    // THEN
    expect(errors).toEqual({ 0: { row: "Overlaps 1 – 10" }, 1: { row: "Overlaps 1 – 10" } });
  });

  it("does not check overlap for a row with an invalid bound", () => {
    // GIVEN
    const rows = [row("1", "10"), row("20", "5")];

    // WHEN
    const errors = validateRangeRows(rows);

    // THEN
    expect(errors).toEqual({ 1: { end: "Must not be lower than start" } });
  });
});

describe("getRangeClipHint", () => {
  const limits = { attribute: "vlan_id", min: 1, max: 4094 };

  it("returns null when the row is inside the limits", () => {
    // GIVEN
    const range = row("1", "4094");

    // WHEN
    const hint = getRangeClipHint(range, limits);

    // THEN
    expect(hint).toBeNull();
  });

  it("returns null when there are no limits", () => {
    // GIVEN
    const range = row("0", "100000");

    // WHEN
    const hint = getRangeClipHint(range, { attribute: "vlan_id", min: null, max: null });

    // THEN
    expect(hint).toBeNull();
  });

  it("returns null when limits are absent", () => {
    // GIVEN
    const range = row("0", "100000");

    // WHEN
    const hint = getRangeClipHint(range, null);

    // THEN
    expect(hint).toBeNull();
  });

  it("returns null for an invalid row", () => {
    // GIVEN
    const range = row("5000", "1");

    // WHEN
    const hint = getRangeClipHint(range, limits);

    // THEN
    expect(hint).toBeNull();
  });

  it("states the clipped bounds with thousands separators", () => {
    // GIVEN
    const range = row("0", "10000");

    // WHEN
    const hint = getRangeClipHint(range, limits);

    // THEN
    expect(hint).toBe("Clipped to 1 – 4,094 by the vlan_id limits");
  });

  it("clips only the bound past a single limit", () => {
    // GIVEN
    const range = row("-10", "10000");

    // WHEN
    const hint = getRangeClipHint(range, { attribute: "asn", min: 1, max: null });

    // THEN
    expect(hint).toBe("Clipped to 1 – 10,000 by the asn limits");
  });

  it("compares a bound above 2^53 with the limits exactly", () => {
    // GIVEN
    const range = row("1", "9223372036854775807");

    // WHEN
    const hint = getRangeClipHint(range, { attribute: "asn", min: 0, max: 4_294_967_295 });

    // THEN
    expect(hint).toBe("Clipped to 1 – 4,294,967,295 by the asn limits");
  });

  it("states that no number can come from a row entirely outside the limits", () => {
    // GIVEN
    const range = row("5000", "6000");

    // WHEN
    const hint = getRangeClipHint(range, limits);

    // THEN
    expect(hint).toBe("Outside the vlan_id limits, so no number can come from it");
  });
});
