import { describe, expect, test } from "vitest";

import type { Sort } from "@/entities/nodes/sort/domain/model/sort";
import { getFieldActiveSort } from "@/entities/nodes/sort/domain/rules/get-field-active-sort";

import {
  generateAttributeSchema,
  generateRelationshipSchema,
} from "../../../../../../tests/fake/schema";

describe("getFieldActiveSort", () => {
  test("returns the sort when it targets the attribute column", () => {
    // GIVEN
    const customSort: Sort[] = [{ field: "name__value", direction: "ASC" }];
    const fieldSchema = generateAttributeSchema({ name: "name", kind: "Text" });

    // WHEN
    const activeSort = getFieldActiveSort(customSort, fieldSchema);

    // THEN
    expect(activeSort).toEqual({ field: "name__value", direction: "ASC" });
  });

  test("returns the sort when it targets a peer attribute of the relationship column", () => {
    // GIVEN
    const customSort: Sort[] = [{ field: "site__name__value", direction: "DESC" }];
    const fieldSchema = generateRelationshipSchema({
      name: "site",
      peer: "LocationSite",
      cardinality: "one",
    });

    // WHEN
    const activeSort = getFieldActiveSort(customSort, fieldSchema);

    // THEN
    expect(activeSort).toEqual({ field: "site__name__value", direction: "DESC" });
  });

  test("does not match the relationship `site` against the attribute field `site_code__value`", () => {
    // GIVEN
    const customSort: Sort[] = [{ field: "site_code__value", direction: "ASC" }];
    const fieldSchema = generateRelationshipSchema({
      name: "site",
      peer: "LocationSite",
      cardinality: "one",
    });

    // WHEN
    const activeSort = getFieldActiveSort(customSort, fieldSchema);

    // THEN
    expect(activeSort).toBeNull();
  });

  test("returns null when the sort targets another attribute column", () => {
    // GIVEN
    const customSort: Sort[] = [{ field: "description__value", direction: "ASC" }];
    const fieldSchema = generateAttributeSchema({ name: "name", kind: "Text" });

    // WHEN
    const activeSort = getFieldActiveSort(customSort, fieldSchema);

    // THEN
    expect(activeSort).toBeNull();
  });

  test("returns null when the custom sort holds several fields", () => {
    // GIVEN
    const customSort: Sort[] = [
      { field: "name__value", direction: "ASC" },
      { field: "description__value", direction: "DESC" },
    ];
    const fieldSchema = generateAttributeSchema({ name: "name", kind: "Text" });

    // WHEN
    const activeSort = getFieldActiveSort(customSort, fieldSchema);

    // THEN
    expect(activeSort).toBeNull();
  });

  test("returns null when there is no custom sort", () => {
    // GIVEN
    const fieldSchema = generateAttributeSchema({ name: "name", kind: "Text" });

    // WHEN
    const activeSort = getFieldActiveSort(null, fieldSchema);

    // THEN
    expect(activeSort).toBeNull();
  });
});
