import { describe, expect, it } from "vitest";

import {
  generateAttributeSchema,
  generateRelationshipSchema,
} from "../../../../../tests/fake/schema";
import { canNumberPoolBeScopedBy } from "./can-number-pool-be-scoped-by";

describe("canNumberPoolBeScopedBy", () => {
  it("accepts a required attribute holding a single value", () => {
    // GIVEN
    const field = generateAttributeSchema({
      name: "encapsulation",
      kind: "Dropdown",
      optional: false,
    });

    // WHEN
    const result = canNumberPoolBeScopedBy(field);

    // THEN
    expect(result).toBe(true);
  });

  it("accepts a required relationship of cardinality one", () => {
    // GIVEN
    const field = generateRelationshipSchema({
      name: "device",
      cardinality: "one",
      optional: false,
    });

    // WHEN
    const result = canNumberPoolBeScopedBy(field);

    // THEN
    expect(result).toBe(true);
  });

  it("refuses an optional attribute, because a node without a value would belong to no sequence", () => {
    // GIVEN
    const field = generateAttributeSchema({ name: "description", kind: "Text", optional: true });

    // WHEN
    const result = canNumberPoolBeScopedBy(field);

    // THEN
    expect(result).toBe(false);
  });

  it("refuses an optional relationship", () => {
    // GIVEN
    const field = generateRelationshipSchema({ name: "rack", cardinality: "one", optional: true });

    // WHEN
    const result = canNumberPoolBeScopedBy(field);

    // THEN
    expect(result).toBe(false);
  });

  it("refuses a relationship of cardinality many", () => {
    // GIVEN
    const field = generateRelationshipSchema({
      name: "tags",
      cardinality: "many",
      optional: false,
    });

    // WHEN
    const result = canNumberPoolBeScopedBy(field);

    // THEN
    expect(result).toBe(false);
  });

  it.each(["List", "JSON", "Any"] as const)(
    "refuses a required %s attribute, because it holds more than one value",
    (kind) => {
      // GIVEN
      const field = generateAttributeSchema({ name: "values", kind, optional: false });

      // WHEN
      const result = canNumberPoolBeScopedBy(field);

      // THEN
      expect(result).toBe(false);
    }
  );
});
