import { describe, expect, it } from "vitest";

import { generateNodeSchema, generateRelationshipSchema } from "../../../../tests/fake/schema";
import { getTemplateRelationshipFromSchema } from "./get-template-relationship-from-schema";

describe("getTemplateRelationshipFromSchema", () => {
  const baseSchema = generateNodeSchema();

  it("should return undefined when schema has no relationships", () => {
    // GIVEN
    const schema = {
      ...baseSchema,
      relationships: undefined,
    };

    // WHEN
    const result = getTemplateRelationshipFromSchema(schema);

    // THEN
    expect(result).toBeUndefined();
  });

  it("should return undefined when schema has empty relationships array", () => {
    // GIVEN
    const schema = {
      ...baseSchema,
      relationships: [],
    };

    // WHEN
    const result = getTemplateRelationshipFromSchema(schema);

    // THEN
    expect(result).toBeUndefined();
  });

  it("should return undefined when schema has no Template relationship", () => {
    // GIVEN
    const schema = {
      ...baseSchema,
      relationships: [
        generateRelationshipSchema({ name: "Other", peer: "OtherKind" }),
        generateRelationshipSchema({ name: "Another", peer: "AnotherKind" }),
      ],
    };

    // WHEN
    const result = getTemplateRelationshipFromSchema(schema);

    // THEN
    expect(result).toBeUndefined();
  });

  it("should return undefined when schema has Template relationship with wrong name", () => {
    // GIVEN
    const schema = {
      ...baseSchema,
      relationships: [
        generateRelationshipSchema({ kind: "Template", name: "wrong_name", peer: "TemplateKind" }),
      ],
    };

    // WHEN
    const result = getTemplateRelationshipFromSchema(schema);

    // THEN
    expect(result).toBeUndefined();
  });

  it("should return undefined when schema has relationship named object_template but wrong kind", () => {
    // GIVEN
    const schema = {
      ...baseSchema,
      relationships: [
        generateRelationshipSchema({
          kind: "Attribute",
          name: "object_template",
          peer: "TemplateKind",
        }),
      ],
    };

    // WHEN
    const result = getTemplateRelationshipFromSchema(schema);

    // THEN
    expect(result).toBeUndefined();
  });

  it("should return Template relationship when schema has one with name object_template", () => {
    // GIVEN
    const templateRelationship = generateRelationshipSchema({
      kind: "Template",
      name: "object_template",
      peer: "TemplateKind",
    });
    const schema = {
      ...baseSchema,
      relationships: [
        generateRelationshipSchema({ name: "Other", peer: "OtherKind" }),
        templateRelationship,
        generateRelationshipSchema({ name: "Another", peer: "AnotherKind" }),
      ],
    };

    // WHEN
    const result = getTemplateRelationshipFromSchema(schema);

    // THEN
    expect(result).toEqual(templateRelationship);
  });
});
