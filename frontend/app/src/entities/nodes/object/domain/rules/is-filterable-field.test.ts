import { describe, expect, it } from "vitest";

import {
  generateAttributeSchema,
  generateRelationshipSchema,
} from "../../../../../../tests/fake/schema";
import { isFilterableField } from "./is-filterable-field";

describe("isFilterableField", () => {
  it.each(["Text", "Number", "Dropdown", "IPAddress"])("should accept a %s attribute", (kind) => {
    // WHEN
    const result = isFilterableField(generateAttributeSchema({ kind }));

    // THEN
    expect(result).toBe(true);
  });

  it.each(["List", "JSON", "Any", "Password", "HashedPassword"])(
    "should reject a %s attribute",
    (kind) => {
      // WHEN
      const result = isFilterableField(generateAttributeSchema({ kind }));

      // THEN
      expect(result).toBe(false);
    }
  );

  it("should accept a relationship", () => {
    // WHEN
    const result = isFilterableField(generateRelationshipSchema());

    // THEN
    expect(result).toBe(true);
  });
});
