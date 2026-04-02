import { describe, expect, it } from "vitest";

import {
  formatAttributeFilterValue,
  getFilterTagDisplay,
} from "@/shared/components/filters/active-filter-tags";

import {
  generateAttributeSchema,
  generateRelationshipSchema,
} from "../../../../tests/fake/schema";

describe("formatAttributeFilterValue", () => {
  it("returns string representation for boolean kind", () => {
    // GIVEN
    const kind = "Boolean" as const;
    const value = true;

    // WHEN
    const result = formatAttributeFilterValue({ kind, value });

    // THEN
    expect(result).toBe("true");
  });

  it("returns the value as-is for text kind", () => {
    // GIVEN
    const kind = "Text" as const;
    const value = "hello";

    // WHEN
    const result = formatAttributeFilterValue({ kind, value });

    // THEN
    expect(result).toBe("hello");
  });
});

describe("getFilterTagDisplay", () => {
  it("returns label and value for attribute value filter", () => {
    // GIVEN
    const fieldSchema = generateAttributeSchema({ name: "hostname", label: "Hostname", kind: "Text" });
    const filter = { name: "hostname__value", value: "server01" };

    // WHEN
    const result = getFilterTagDisplay({
      filter,
      fieldKey: "value",
      fieldSchema,
      isRelationship: false,
    });

    // THEN
    expect(result).toEqual({
      label: "Hostname",
      condition: "contains",
      value: "server01",
    });
  });

  it("returns null for value filter on a relationship schema", () => {
    // GIVEN
    const fieldSchema = generateRelationshipSchema({ name: "site" });
    const filter = { name: "site__value", value: "test" };

    // WHEN
    const result = getFilterTagDisplay({
      filter,
      fieldKey: "value",
      fieldSchema,
      isRelationship: true,
    });

    // THEN
    expect(result).toBeNull();
  });

  it("returns display labels for relationship ids filter", () => {
    // GIVEN
    const fieldSchema = generateRelationshipSchema({ name: "site", label: "Site" });
    const filter = {
      name: "site__ids",
      value: [
        { id: "1", display_label: "Site A" },
        { id: "2", display_label: "Site B" },
      ],
    };

    // WHEN
    const result = getFilterTagDisplay({
      filter,
      fieldKey: "ids",
      fieldSchema,
      isRelationship: true,
    });

    // THEN
    expect(result).toEqual({
      label: "Site",
      condition: "is any of",
      value: "Site A, Site B",
    });
  });

  it("returns null for ids filter on non-relationship", () => {
    // GIVEN
    const fieldSchema = generateAttributeSchema({ name: "name" });
    const filter = { name: "name__ids", value: ["a"] };

    // WHEN
    const result = getFilterTagDisplay({
      filter,
      fieldKey: "ids",
      fieldSchema,
      isRelationship: false,
    });

    // THEN
    expect(result).toBeNull();
  });

  it("returns is empty condition for isnull filter with true value", () => {
    // GIVEN
    const fieldSchema = generateAttributeSchema({ name: "description", label: "Description" });
    const filter = { name: "description__isnull", value: true };

    // WHEN
    const result = getFilterTagDisplay({
      filter,
      fieldKey: "isnull",
      fieldSchema,
      isRelationship: false,
    });

    // THEN
    expect(result).toEqual({
      label: "Description",
      condition: "is empty",
      value: "",
    });
  });

  it("returns is not empty condition for isnull filter with false value", () => {
    // GIVEN
    const fieldSchema = generateAttributeSchema({ name: "description", label: "Description" });
    const filter = { name: "description__isnull", value: false };

    // WHEN
    const result = getFilterTagDisplay({
      filter,
      fieldKey: "isnull",
      fieldSchema,
      isRelationship: false,
    });

    // THEN
    expect(result).toEqual({
      label: "Description",
      condition: "is not empty",
      value: "",
    });
  });

  it("returns null for unknown field key", () => {
    // GIVEN
    const fieldSchema = generateAttributeSchema({ name: "name" });
    const filter = { name: "name__unknown", value: "test" };

    // WHEN
    const result = getFilterTagDisplay({
      filter,
      fieldKey: "unknown",
      fieldSchema,
      isRelationship: false,
    });

    // THEN
    expect(result).toBeNull();
  });
});
