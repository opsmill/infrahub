import { getFiltersFromFormData } from "@/components/filters/utils/getFiltersFromFormData";
import { FormFieldValue } from "@/components/form/type";
import { describe, expect } from "vitest";

describe("getFiltersFromFormData - test", () => {
  it("returns an attribute value correctly", () => {
    // GIVEN
    const formData: Record<string, FormFieldValue> = {
      field1: { source: { type: "user" }, value: "value1" },
    };

    // WHEN
    const filters = getFiltersFromFormData(formData);

    // THEN
    expect(filters).toHaveLength(1);
    expect(filters[0]).toEqual({
      name: "field1__value",
      value: "value1",
    });
  });

  it("returns a relationship of cardinality one's value correctly", () => {
    // GIVEN
    const formData: Record<string, FormFieldValue> = {
      relationship1: { source: { type: "user" }, value: { id: "relationship-id" } },
    };

    // WHEN
    const filters = getFiltersFromFormData(formData);

    // THEN
    expect(filters).toHaveLength(1);
    expect(filters[0]).toEqual({
      name: "relationship1__ids",
      value: ["relationship-id"],
    });
  });

  it("returns a relationship of cardinality many's value correctly", () => {
    // GIVEN
    const formData: Record<string, FormFieldValue> = {
      relationship2: { source: { type: "user" }, value: [{ id: "relationship-id" }] },
    };

    // WHEN
    const filters = getFiltersFromFormData(formData);

    // THEN
    expect(filters).toHaveLength(1);
    expect(filters[0]).toEqual({
      name: "relationship2__ids",
      value: ["relationship-id"],
    });
  });

  it("ignores filter when value is an empty array", () => {
    // GIVEN
    const formData: Record<string, FormFieldValue> = {
      field1: { source: { type: "user" }, value: [] },
    };

    // WHEN
    const filters = getFiltersFromFormData(formData);

    // THEN
    expect(filters).toHaveLength(0);
  });
});
