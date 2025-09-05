import { beforeEach, describe, expect, it } from "vitest";

import { store } from "@/shared/stores";

import {
  genericSchemasAtom,
  nodeSchemasAtom,
  profileSchemasAtom,
  templateSchemasAtom,
} from "@/entities/schema/stores/schema.atom";

import {
  generateGenericSchema,
  generateNodeSchema,
  generateProfileSchema,
  generateTemplateSchema,
} from "../../../../tests/fake/schema";
import { getSchema } from "./get-schema";

describe("getSchema", () => {
  const nodeSchema = generateNodeSchema({ kind: "Node" });
  const genericSchema = generateGenericSchema({ kind: "Generic" });
  const profileSchema = generateProfileSchema({ kind: "Profile" });
  const templateSchema = generateTemplateSchema({ kind: "Template" });

  beforeEach(() => {
    store.set(nodeSchemasAtom, [nodeSchema]);
    store.set(genericSchemasAtom, [genericSchema]);
    store.set(profileSchemasAtom, [profileSchema]);
    store.set(templateSchemasAtom, [templateSchema]);
  });

  it("should return null schema when no kind is provided", () => {
    const result = getSchema();
    expect(result).toEqual({
      schema: null,
      isGeneric: false,
      isNode: false,
      isProfile: false,
      isTemplate: false,
    });
  });

  it("should return node schema when kind matches a node", () => {
    const result = getSchema("Node");
    expect(result).toEqual({
      schema: nodeSchema,
      isGeneric: false,
      isNode: true,
      isProfile: false,
      isTemplate: false,
    });
  });

  it("should return generic schema when kind matches a generic", () => {
    const result = getSchema("Generic");
    expect(result).toEqual({
      schema: genericSchema,
      isGeneric: true,
      isNode: false,
      isProfile: false,
      isTemplate: false,
    });
  });

  it("should return profile schema when kind matches a profile", () => {
    const result = getSchema("Profile");
    expect(result).toEqual({
      schema: profileSchema,
      isGeneric: false,
      isNode: false,
      isProfile: true,
      isTemplate: false,
    });
  });

  it("should return template schema when kind matches a template", () => {
    const result = getSchema("Template");
    expect(result).toEqual({
      schema: templateSchema,
      isGeneric: false,
      isNode: false,
      isProfile: false,
      isTemplate: true,
    });
  });

  it("should return null schema when kind doesn't match any schema", () => {
    const result = getSchema("NonExistent");
    expect(result).toEqual({
      schema: null,
      isGeneric: false,
      isNode: false,
      isProfile: false,
      isTemplate: false,
    });
  });
});
