import { describe, expect, it } from "vitest";

import { isFieldFiltered } from "@/shared/hooks/is-field-filtered";

describe("isFieldFiltered", () => {
  it("returns true for exact field name match", () => {
    // GIVEN
    const filter = { name: "status", value: "active" };

    // WHEN
    const result = isFieldFiltered(filter, "status");

    // THEN
    expect(result).toBe(true);
  });

  it("returns true when filter name starts with fieldName followed by '__'", () => {
    // GIVEN
    const filter = { name: "status__value", value: "active" };

    // WHEN
    const result = isFieldFiltered(filter, "status");

    // THEN
    expect(result).toBe(true);
  });

  it("returns false when filter does not match the field", () => {
    // GIVEN
    const filter = { name: "name__value", value: "test" };

    // WHEN
    const result = isFieldFiltered(filter, "status");

    // THEN
    expect(result).toBe(false);
  });

  it("does not false-match field name prefixes", () => {
    // GIVEN
    const filter = { name: "namespace__value", value: "test" };

    // WHEN
    const result = isFieldFiltered(filter, "name");

    // THEN
    expect(result).toBe(false);
  });
});
