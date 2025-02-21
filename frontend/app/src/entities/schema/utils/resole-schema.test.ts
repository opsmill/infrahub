import { GenericSchema, NodeSchema, ProfileSchema } from "@/entities/schema/types";
import { describe, expect, it } from "vitest";
import {
  generateGenericSchema,
  generateNodeSchema,
  generateProfileSchema,
} from "../../../../tests/fake/schema";
import { resolveSchema } from "./resolve-schema";

describe("resolveSchema", () => {
  const baseNodeSchema: NodeSchema = generateNodeSchema();
  const baseGenericSchema: GenericSchema = generateGenericSchema();
  const baseProfileSchema: ProfileSchema = generateProfileSchema();

  it("should return null schema when kind is null", () => {
    // GIVEN
    const schemas = {
      nodeSchemas: [baseNodeSchema],
      genericSchemas: [baseGenericSchema],
      profileSchemas: [baseProfileSchema],
    };

    // WHEN
    const result = resolveSchema(null, schemas);

    // THEN
    expect(result).toEqual({
      schema: null,
      isGeneric: false,
      isNode: false,
      isProfile: false,
    });
  });

  it("should return null schema when kind is undefined", () => {
    // GIVEN
    const schemas = {
      nodeSchemas: [baseNodeSchema],
      genericSchemas: [baseGenericSchema],
      profileSchemas: [baseProfileSchema],
    };

    // WHEN
    const result = resolveSchema(undefined, schemas);

    // THEN
    expect(result).toEqual({
      schema: null,
      isGeneric: false,
      isNode: false,
      isProfile: false,
    });
  });

  it("should return node schema when kind matches a node schema", () => {
    // GIVEN
    const nodeSchema = {
      ...baseNodeSchema,
      kind: "SpecificNode",
    };
    const schemas = {
      nodeSchemas: [nodeSchema],
      genericSchemas: [baseGenericSchema],
      profileSchemas: [baseProfileSchema],
    };

    // WHEN
    const result = resolveSchema("SpecificNode", schemas);

    // THEN
    expect(result).toEqual({
      schema: nodeSchema,
      isGeneric: false,
      isNode: true,
      isProfile: false,
    });
  });

  it("should return generic schema when kind matches a generic schema", () => {
    // GIVEN
    const genericSchema = {
      ...baseGenericSchema,
      kind: "SpecificGeneric",
    };
    const schemas = {
      nodeSchemas: [],
      genericSchemas: [genericSchema],
      profileSchemas: [baseProfileSchema],
    };

    // WHEN
    const result = resolveSchema("SpecificGeneric", schemas);

    // THEN
    expect(result).toEqual({
      schema: genericSchema,
      isGeneric: true,
      isNode: false,
      isProfile: false,
    });
  });

  it("should return profile schema when kind matches a profile schema", () => {
    // GIVEN
    const profileSchema = {
      ...baseProfileSchema,
      kind: "SpecificProfile",
    };
    const schemas = {
      nodeSchemas: [],
      genericSchemas: [],
      profileSchemas: [profileSchema],
    };

    // WHEN
    const result = resolveSchema("SpecificProfile", schemas);

    // THEN
    expect(result).toEqual({
      schema: profileSchema,
      isGeneric: false,
      isNode: false,
      isProfile: true,
    });
  });

  it("should return null schema when kind doesn't match any schema", () => {
    // GIVEN
    const schemas = {
      nodeSchemas: [{ ...baseNodeSchema, kind: "ExistingNode" }],
      genericSchemas: [{ ...baseGenericSchema, kind: "ExistingGeneric" }],
      profileSchemas: [{ ...baseProfileSchema, kind: "ExistingProfile" }],
    };

    // WHEN
    const result = resolveSchema("NonExistentKind", schemas);

    // THEN
    expect(result).toEqual({
      schema: null,
      isGeneric: false,
      isNode: false,
      isProfile: false,
    });
  });
});
