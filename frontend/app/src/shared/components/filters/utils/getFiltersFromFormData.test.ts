import { describe, expect } from "vitest";

import { getFiltersFromFormData } from "@/shared/components/filters/utils/getFiltersFromFormData";
import type { FormFieldValue } from "@/shared/components/form/type";

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

  it("returns an attribute of kind list value correctly", () => {
    // GIVEN
    const formData: Record<string, FormFieldValue> = {
      field1: { source: { type: "user" }, value: ["value1"] },
    };

    // WHEN
    const filters = getFiltersFromFormData(formData);

    // THEN
    expect(filters).toHaveLength(1);
    expect(filters[0]).toEqual({
      name: "field1__values",
      value: ["value1"],
    });
  });

  it("returns a relationship of cardinality one's value correctly", () => {
    // GIVEN
    const formData: Record<string, FormFieldValue> = {
      relationship1: {
        source: { type: "user" },
        value: { id: "relationship-id", display_label: "label", __typename: "peer" },
      },
    };

    // WHEN
    const filters = getFiltersFromFormData(formData);

    // THEN
    expect(filters).toHaveLength(1);
    expect(filters[0]).toEqual({
      name: "relationship1__ids",
      value: [{ id: "relationship-id", display_label: "label", __typename: "peer" }],
    });
  });

  it("returns a relationship of cardinality many's value correctly", () => {
    // GIVEN
    const formData: Record<string, FormFieldValue> = {
      relationship2: {
        source: { type: "user" },
        value: [{ id: "relationship-id", display_label: "label", __typename: "peer" }],
      },
    };

    // WHEN
    const filters = getFiltersFromFormData(formData);

    // THEN
    expect(filters).toHaveLength(1);
    expect(filters[0]).toEqual({
      name: "relationship2__ids",
      value: [{ id: "relationship-id", display_label: "label", __typename: "peer" }],
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
