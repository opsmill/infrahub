import { describe, expect, it } from "vitest";

import type { Filter } from "@/shared/hooks/useFilters";

import { getFilterPickerCount } from "@/entities/nodes/object/domain/get-filter-picker-count";

import {
  generateAttributeSchema,
  generateNodeSchema,
  generateRelationshipSchema,
} from "../../../../../tests/fake/schema";

describe("getFilterPickerCount", () => {
  it("counts filters matching schema attributes", () => {
    // GIVEN
    const schema = generateNodeSchema({
      attributes: [
        generateAttributeSchema({ name: "name" }),
        generateAttributeSchema({ name: "status" }),
      ],
    });
    const filters: Filter[] = [
      { name: "name__value", value: "test" },
      { name: "status__value", value: "active" },
    ];

    // WHEN
    const result = getFilterPickerCount(schema, filters);

    // THEN
    expect(result).toBe(2);
  });

  it("counts filters matching schema relationships", () => {
    // GIVEN
    const schema = generateNodeSchema({
      relationships: [generateRelationshipSchema({ name: "parent" })],
    });
    const filters: Filter[] = [{ name: "parent__ids", value: ["some-id"] }];

    // WHEN
    const result = getFilterPickerCount(schema, filters);

    // THEN
    expect(result).toBe(1);
  });

  it("counts metadata filters", () => {
    // GIVEN
    const schema = generateNodeSchema();
    const filters: Filter[] = [
      { name: "node_metadata__created_at__after", value: "2024-01-01" },
      { name: "node_metadata__updated_by__ids", value: ["id"] },
    ];

    // WHEN
    const result = getFilterPickerCount(schema, filters);

    // THEN
    expect(result).toBe(2);
  });

  it("excludes non-menu filters", () => {
    // GIVEN
    const schema = generateNodeSchema({
      attributes: [generateAttributeSchema({ name: "name" })],
    });
    const filters: Filter[] = [
      { name: "name__value", value: "test" },
      { name: "include_available", value: true },
      { name: "order", value: "name__asc" },
      { name: "group_type__value", value: "default" },
    ];

    // WHEN
    const result = getFilterPickerCount(schema, filters);

    // THEN
    expect(result).toBe(1);
  });

  it("does not false-match field name prefixes", () => {
    // GIVEN
    const schema = generateNodeSchema({
      attributes: [generateAttributeSchema({ name: "name" })],
    });
    const filters: Filter[] = [{ name: "namespace__value", value: "test" }];

    // WHEN
    const result = getFilterPickerCount(schema, filters);

    // THEN
    expect(result).toBe(0);
  });

  it("returns 0 when no filters match menu fields", () => {
    // GIVEN
    const schema = generateNodeSchema();
    const filters: Filter[] = [
      { name: "include_available", value: false },
      { name: "order", value: "name__asc" },
    ];

    // WHEN
    const result = getFilterPickerCount(schema, filters);

    // THEN
    expect(result).toBe(0);
  });
});
