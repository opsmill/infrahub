import { describe, expect, it } from "vitest";

import { SORT_DIRECTION, type Sort } from "@/entities/nodes/sort/domain/model/sort";
import { parseSortToken, serializeSortToken } from "@/entities/nodes/sort/domain/rules/sort-token";

describe("parseSortToken", () => {
  it("extracts the field and direction from a suffixed token", () => {
    // GIVEN
    const ascToken = "label__asc";
    const descToken = "label__desc";

    // WHEN
    const ascSort = parseSortToken(ascToken);
    const descSort = parseSortToken(descToken);

    // THEN
    expect(ascSort).toEqual({ field: "label", direction: SORT_DIRECTION.ASC });
    expect(descSort).toEqual({ field: "label", direction: SORT_DIRECTION.DESC });
  });

  it("keeps `__` inside the field path and only strips the trailing direction", () => {
    // GIVEN
    const token = "name__value__desc";

    // WHEN
    const sort = parseSortToken(token);

    // THEN
    expect(sort).toEqual({ field: "name__value", direction: SORT_DIRECTION.DESC });
  });

  it("treats a token without a direction suffix as a bare field sorted ASC", () => {
    // GIVEN
    const schemaOrderByEntry = "name__value";
    const singleSegment = "name";

    // WHEN
    const entrySort = parseSortToken(schemaOrderByEntry);
    const singleSegmentSort = parseSortToken(singleSegment);

    // THEN
    expect(entrySort).toEqual({ field: "name__value", direction: SORT_DIRECTION.ASC });
    expect(singleSegmentSort).toEqual({ field: "name", direction: SORT_DIRECTION.ASC });
  });

  it("treats a token that is only a direction suffix as a bare field, never an empty one", () => {
    // GIVEN
    const ascOnly = "__asc";
    const descOnly = "__desc";

    // WHEN
    const ascSort = parseSortToken(ascOnly);
    const descSort = parseSortToken(descOnly);

    // THEN
    expect(ascSort).toEqual({ field: "__asc", direction: SORT_DIRECTION.ASC });
    expect(descSort).toEqual({ field: "__desc", direction: SORT_DIRECTION.ASC });
  });

  it("ignores an uppercase or unknown direction suffix", () => {
    // GIVEN
    const uppercase = "name__value__DESC";
    const unknown = "name__value__descending";

    // WHEN
    const uppercaseSort = parseSortToken(uppercase);
    const unknownSort = parseSortToken(unknown);

    // THEN
    expect(uppercaseSort).toEqual({ field: "name__value__DESC", direction: SORT_DIRECTION.ASC });
    expect(unknownSort).toEqual({
      field: "name__value__descending",
      direction: SORT_DIRECTION.ASC,
    });
  });

  it("returns hostile URL input verbatim as a field instead of throwing", () => {
    // GIVEN
    const empty = "";
    const injection = "name__value: ASC}) {password__desc";

    // WHEN
    const emptySort = parseSortToken(empty);
    const injectionSort = parseSortToken(injection);

    // THEN
    expect(emptySort).toEqual({ field: "", direction: SORT_DIRECTION.ASC });
    expect(injectionSort).toEqual({
      field: "name__value: ASC}) {password",
      direction: SORT_DIRECTION.DESC,
    });
  });
});

describe("serializeSortToken", () => {
  it("joins the field and the lowercased direction with `__`", () => {
    // GIVEN
    const ascSort: Sort = { field: "name__value", direction: SORT_DIRECTION.ASC };
    const descSort: Sort = { field: "name__value", direction: SORT_DIRECTION.DESC };

    // WHEN
    const ascToken = serializeSortToken(ascSort);
    const descToken = serializeSortToken(descSort);

    // THEN
    expect(ascToken).toBe("name__value__asc");
    expect(descToken).toBe("name__value__desc");
  });

  it("round-trips through parseSortToken", () => {
    // GIVEN
    const ascSort: Sort = { field: "name__value", direction: SORT_DIRECTION.ASC };
    const descSort: Sort = { field: "name__value", direction: SORT_DIRECTION.DESC };

    // WHEN
    const ascRoundTrip = parseSortToken(serializeSortToken(ascSort));
    const descRoundTrip = parseSortToken(serializeSortToken(descSort));

    // THEN
    expect(ascRoundTrip).toEqual(ascSort);
    expect(descRoundTrip).toEqual(descSort);
  });
});
