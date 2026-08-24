import { describe, expect, it } from "vitest";

import { isRelationshipSchema } from "@/entities/schema/domain/rules/is-relationship-schema";

import {
  generateAttributeSchema,
  generateRelationshipSchema,
} from "../../../../../tests/fake/schema";

describe("isRelationshipSchema", () => {
  it("should return true for a relationship schema", () => {
    // GIVEN
    const schema = generateRelationshipSchema();

    // WHEN
    const result = isRelationshipSchema(schema);

    // THEN
    expect(result).toBe(true);
  });

  it("should return false for an attribute schema", () => {
    // GIVEN
    const schema = generateAttributeSchema();

    // WHEN
    const result = isRelationshipSchema(schema);

    // THEN
    expect(result).toBe(false);
  });
});
