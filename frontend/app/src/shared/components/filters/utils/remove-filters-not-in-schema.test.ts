import { describe, expect, it } from "vitest";

import type { Filter } from "@/shared/hooks/useFilters";

import {
  generateAttributeSchema,
  generateGenericSchema,
  generateRelationshipSchema,
} from "../../../../../tests/fake/schema";
import { removeFiltersNotInSchema } from "./remove-filters-not-in-schema";

const mockSchema = generateGenericSchema({
  attributes: [
    generateAttributeSchema({ name: "attr1" }),
    generateAttributeSchema({ name: "attr2" }),
  ],
  relationships: [
    generateRelationshipSchema({ name: "rel1" }),
    generateRelationshipSchema({ name: "rel2" }),
  ],
});

describe("removeFiltersNotInSchema", () => {
  it("should return empty array for empty filters", () => {
    // GIVEN
    const filters: Filter[] = [];

    // WHEN
    const result = removeFiltersNotInSchema(filters, mockSchema);

    // THEN
    expect(result).toEqual([]);
  });

  it("should return empty array for schema without fields", () => {
    // GIVEN
    const schemaWithNoFields = generateGenericSchema({ attributes: [], relationships: [] });
    const filters: Filter[] = [{ name: "attr1__value", value: "test" }];

    // WHEN
    const result = removeFiltersNotInSchema(filters, schemaWithNoFields);

    // THEN
    expect(result).toEqual([]);
  });

  it("should keep filters matching schema attributes", () => {
    // GIVEN
    const filters: Filter[] = [{ name: "attr1__value", value: "test" }];

    // WHEN
    const result = removeFiltersNotInSchema(filters, mockSchema);

    // THEN
    expect(result).toEqual(filters);
  });

  it("should keep filters matching schema relationships", () => {
    // GIVEN
    const filters: Filter[] = [{ name: "rel1__value", value: "test" }];

    // WHEN
    const result = removeFiltersNotInSchema(filters, mockSchema);

    // THEN
    expect(result).toEqual(filters);
  });

  it("should remove filters not in schema", () => {
    // GIVEN
    const filters: Filter[] = [{ name: "nonexistent__value", value: "test" }];

    // WHEN
    const result = removeFiltersNotInSchema(filters, mockSchema);

    // THEN
    expect(result).toEqual([]);
  });

  it("should handle mix of matching and non-matching filters", () => {
    // GIVEN
    const filters: Filter[] = [
      { name: "attr1__value", value: "test" },
      { name: "nonexistent__value", value: "test" },
      { name: "rel2__value", value: "test" },
    ];
    const expectedFilters: Filter[] = [
      { name: "attr1__value", value: "test" },
      { name: "rel2__value", value: "test" },
    ];

    // WHEN
    const result = removeFiltersNotInSchema(filters, mockSchema);

    // THEN
    expect(result).toEqual(expectedFilters);
  });

  it("should handle schema with only attributes", () => {
    // GIVEN
    const schemaWithOnlyAttrs = generateGenericSchema({
      ...mockSchema,
      relationships: [],
    });
    const filters: Filter[] = [
      { name: "attr1__value", value: "test" },
      { name: "rel1__value", value: "test" },
    ];
    const expectedFilters: Filter[] = [{ name: "attr1__value", value: "test" }];

    // WHEN
    const result = removeFiltersNotInSchema(filters, schemaWithOnlyAttrs);

    // THEN
    expect(result).toEqual(expectedFilters);
  });

  it("should handle schema with only relationships", () => {
    // GIVEN
    const schemaWithOnlyRels = generateGenericSchema({
      ...mockSchema,
      attributes: [],
    });
    const filters: Filter[] = [
      { name: "attr1__value", value: "test" },
      { name: "rel1__value", value: "test" },
    ];
    const expectedFilters: Filter[] = [{ name: "rel1__value", value: "test" }];

    // WHEN
    const result = removeFiltersNotInSchema(filters, schemaWithOnlyRels);

    // THEN
    expect(result).toEqual(expectedFilters);
  });
});
