import { genericsState, profilesAtom, schemaState } from "@/entities/schema/stores/schema.atom";
import { store } from "@/shared/stores";
import { beforeEach, describe, expect, it } from "vitest";
import {
  generateGenericSchema,
  generateNodeSchema,
  generateProfileSchema,
} from "../../../../tests/fake/schema";
import { getSchema } from "./get-schema";

describe("getSchema", () => {
  const nodeSchema = generateNodeSchema({ kind: "Node" });
  const genericSchema = generateGenericSchema({ kind: "Generic" });
  const profileSchema = generateProfileSchema({ kind: "Profile" });

  beforeEach(() => {
    store.set(schemaState, [nodeSchema]);

    store.set(genericsState, [genericSchema]);

    store.set(profilesAtom, [profileSchema]);
  });

  it("should return null schema when no kind is provided", () => {
    const result = getSchema();
    expect(result).toEqual({
      schema: null,
      isGeneric: false,
      isNode: false,
      isProfile: false,
    });
  });

  it("should return node schema when kind matches a node", () => {
    const result = getSchema("Node");
    expect(result).toEqual({
      schema: nodeSchema,
      isGeneric: false,
      isNode: true,
      isProfile: false,
    });
  });

  it("should return generic schema when kind matches a generic", () => {
    const result = getSchema("Generic");
    expect(result).toEqual({
      schema: genericSchema,
      isGeneric: true,
      isNode: false,
      isProfile: false,
    });
  });

  it("should return profile schema when kind matches a profile", () => {
    const result = getSchema("Profile");
    expect(result).toEqual({
      schema: profileSchema,
      isGeneric: false,
      isNode: false,
      isProfile: true,
    });
  });

  it("should return null schema when kind doesn't match any schema", () => {
    const result = getSchema("NonExistent");
    expect(result).toEqual({
      schema: null,
      isGeneric: false,
      isNode: false,
      isProfile: false,
    });
  });
});
