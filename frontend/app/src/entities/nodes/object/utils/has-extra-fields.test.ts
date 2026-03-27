import { describe, expect, it } from "vitest";

import { hasExtraFields } from "@/entities/nodes/object/utils/has-extra-fields";
import type { ModelSchema } from "@/entities/schema/types";

import {
  generateAttributeSchema,
  generateNodeSchema,
  generateRelationshipSchema,
} from "../../../../../tests/fake/schema";

describe("hasExtraFields", () => {
  it("should return true when an attribute has display 'extra'", () => {
    // GIVEN
    const schema = generateNodeSchema({
      attributes: [generateAttributeSchema({ display: "extra" })],
      relationships: [],
    });

    // WHEN
    const result = hasExtraFields(schema);

    // THEN
    expect(result).toBe(true);
  });

  it("should return true when a relationship has display 'extra'", () => {
    // GIVEN
    const schema = generateNodeSchema({
      attributes: [],
      relationships: [generateRelationshipSchema({ display: "extra" })],
    });

    // WHEN
    const result = hasExtraFields(schema);

    // THEN
    expect(result).toBe(true);
  });

  it("should return false when no fields have display 'extra'", () => {
    // GIVEN
    const schema = generateNodeSchema({
      attributes: [generateAttributeSchema({ display: "default" })],
      relationships: [generateRelationshipSchema({ display: "default" })],
    });

    // WHEN
    const result = hasExtraFields(schema);

    // THEN
    expect(result).toBe(false);
  });

  it("should return false when attributes and relationships are empty arrays", () => {
    // GIVEN
    const schema = generateNodeSchema({
      attributes: [],
      relationships: [],
    });

    // WHEN
    const result = hasExtraFields(schema);

    // THEN
    expect(result).toBe(false);
  });

  it("should return false when attributes and relationships are undefined", () => {
    // GIVEN
    const schema = generateNodeSchema();
    const schemaWithoutFields = {
      ...schema,
      attributes: undefined,
      relationships: undefined,
    } as ModelSchema;

    // WHEN
    const result = hasExtraFields(schemaWithoutFields);

    // THEN
    expect(result).toBe(false);
  });

  it("should return true when only one attribute among many has display 'extra'", () => {
    // GIVEN
    const schema = generateNodeSchema({
      attributes: [
        generateAttributeSchema({ display: "default" }),
        generateAttributeSchema({ display: "extra" }),
        generateAttributeSchema({ display: "default" }),
      ],
      relationships: [],
    });

    // WHEN
    const result = hasExtraFields(schema);

    // THEN
    expect(result).toBe(true);
  });

  it("should return true when only one relationship among many has display 'extra'", () => {
    // GIVEN
    const schema = generateNodeSchema({
      attributes: [],
      relationships: [
        generateRelationshipSchema({ display: "default" }),
        generateRelationshipSchema({ display: "extra" }),
      ],
    });

    // WHEN
    const result = hasExtraFields(schema);

    // THEN
    expect(result).toBe(true);
  });

  it("should return true when both attributes and relationships have display 'extra'", () => {
    // GIVEN
    const schema = generateNodeSchema({
      attributes: [generateAttributeSchema({ display: "extra" })],
      relationships: [generateRelationshipSchema({ display: "extra" })],
    });

    // WHEN
    const result = hasExtraFields(schema);

    // THEN
    expect(result).toBe(true);
  });
});
