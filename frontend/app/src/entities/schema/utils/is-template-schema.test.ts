import { describe, expect, it } from "vitest";

import { isTemplateSchema } from "@/entities/schema/utils/is-template-schema";

import { generateNodeSchema, generateTemplateSchema } from "../../../../tests/fake/schema";

describe("isTemplateSchema", () => {
  it("should return true for a template schema", () => {
    // GIVEN
    const schema = generateTemplateSchema({ namespace: "Template" });

    // WHEN
    const result = isTemplateSchema(schema);

    // THEN
    expect(result).toBe(true);
  });

  it("should return false for a non-template schema", () => {
    // GIVEN
    const schema = generateNodeSchema({ namespace: "Other" });

    // WHEN
    const result = isTemplateSchema(schema);

    // THEN
    expect(result).toBe(false);
  });

  it("should return false for schema with undefined namespace", () => {
    // GIVEN
    const schema = generateNodeSchema({ namespace: undefined });

    // WHEN
    const result = isTemplateSchema(schema);

    // THEN
    expect(result).toBe(false);
  });

  it("should return false for schema with null namespace", () => {
    // GIVEN
    const schema = generateNodeSchema({ namespace: null! });

    // WHEN
    const result = isTemplateSchema(schema);

    // THEN
    expect(result).toBe(false);
  });

  it("should return false for schema with empty string namespace", () => {
    // GIVEN
    const schema = generateNodeSchema({ namespace: "" });

    // WHEN
    const result = isTemplateSchema(schema);

    // THEN
    expect(result).toBe(false);
  });

  it("should return false for schema with case-different namespace 'template'", () => {
    // GIVEN
    const schema = generateNodeSchema({ namespace: "template" });

    // WHEN
    const result = isTemplateSchema(schema);

    // THEN
    expect(result).toBe(false);
  });
});
