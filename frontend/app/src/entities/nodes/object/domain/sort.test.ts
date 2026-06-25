import { describe, expect, test } from "vitest";

import {
  formatSort,
  getSortDirection,
  getSortField,
  getValidSort,
  parseSort,
  type Sort,
} from "@/entities/nodes/object/domain/sort";
import type { SortFieldKey } from "@/entities/nodes/object/domain/sortable-field";

const SORTABLE = new Set<SortFieldKey>([
  "name__value",
  "owner__name__value",
  "node_metadata__created_at",
  "node_metadata__updated_at",
]);

describe("getSortField", () => {
  test("strips a trailing direction suffix", () => {
    // GIVEN / WHEN / THEN
    expect(getSortField("name__value__asc")).toBe("name__value");
    expect(getSortField("node_metadata__updated_at__desc")).toBe("node_metadata__updated_at");
  });
});

describe("getSortDirection", () => {
  test("reads the uppercase direction from the lowercase suffix", () => {
    // GIVEN / WHEN / THEN
    expect(getSortDirection("name__value__desc")).toBe("DESC");
    expect(getSortDirection("name__value__asc")).toBe("ASC");
  });

  test("defaults to ASC when the suffix is absent", () => {
    // GIVEN / WHEN / THEN
    expect(getSortDirection("owner__name__value")).toBe("ASC");
  });
});

describe("parseSort", () => {
  test("splits a token into its field key and uppercase direction", () => {
    // GIVEN / WHEN / THEN
    expect(parseSort("owner__name__value__desc")).toEqual({
      field: "owner__name__value",
      direction: "DESC",
    });
  });

  test("round-trips with formatSort", () => {
    // GIVEN
    const sort = parseSort("name__value__asc");
    // WHEN / THEN
    expect(formatSort(sort.field, sort.direction)).toBe("name__value__asc");
  });
});

describe("formatSort", () => {
  test("joins a field and uppercase direction into a lowercase token", () => {
    // GIVEN / WHEN / THEN
    expect(formatSort("name__value", "DESC")).toBe("name__value__desc");
  });

  test("round-trips with getSortField and getSortDirection", () => {
    // GIVEN
    const sort = formatSort("owner__name__value", "ASC");
    // WHEN / THEN
    expect(getSortField(sort)).toBe("owner__name__value");
    expect(getSortDirection(sort)).toBe("ASC");
  });
});

describe("getValidSort", () => {
  const nameAsc: Sort = { field: "name__value", direction: "ASC" };
  const ownerDesc: Sort = { field: "owner__name__value", direction: "DESC" };
  const createdAsc: Sort = { field: "node_metadata__created_at", direction: "ASC" };

  test("returns null when there is no sort", () => {
    // GIVEN / WHEN / THEN
    expect(getValidSort(null, SORTABLE)).toBeNull();
    expect(getValidSort([], SORTABLE)).toBeNull();
  });

  test("keeps schema-compatible entries in order", () => {
    // GIVEN / WHEN
    const result = getValidSort([ownerDesc, nameAsc], SORTABLE);
    // THEN
    expect(result).toEqual([ownerDesc, nameAsc]);
  });

  test("excludes entries whose field is not sortable in the schema", () => {
    // GIVEN
    const sorts: Sort[] = [nameAsc, { field: "gone__value", direction: "DESC" }, createdAsc];
    // WHEN
    const result = getValidSort(sorts, SORTABLE);
    // THEN
    expect(result).toEqual([nameAsc, createdAsc]);
  });

  test("returns null when every entry is invalid", () => {
    // GIVEN
    const sorts: Sort[] = [
      { field: "gone__value", direction: "ASC" },
      { field: "also_gone__value", direction: "DESC" },
    ];
    // WHEN / THEN
    expect(getValidSort(sorts, SORTABLE)).toBeNull();
  });

  test("drops duplicate fields, keeping the first", () => {
    // GIVEN
    const sorts: Sort[] = [nameAsc, { field: "name__value", direction: "DESC" }];
    // WHEN
    const result = getValidSort(sorts, SORTABLE);
    // THEN
    expect(result).toEqual([nameAsc]);
  });

  test("includes an entry once its field becomes sortable again", () => {
    // GIVEN
    const teamDesc: Sort = { field: "team__name__value", direction: "DESC" };
    expect(getValidSort([teamDesc, nameAsc], SORTABLE)).toEqual([nameAsc]);

    // WHEN
    const widened = new Set<SortFieldKey>([...SORTABLE, "team__name__value"]);

    // THEN
    expect(getValidSort([teamDesc, nameAsc], widened)).toEqual([teamDesc, nameAsc]);
  });
});
