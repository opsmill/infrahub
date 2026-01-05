import { describe, expect, it } from "vitest";

import {
  getObjectAttributes,
  getObjectRelationships,
  getSchemaObjectColumns,
} from "@/entities/nodes/object-items/getSchemaObjectColumns";

import {
  C_deviceAttributeListColumns,
  C_deviceObjectColumns,
  C_deviceProfileColumns,
  C_deviceRelationshipColumns,
  C_deviceSchema,
} from "../data/deviceSchema";

describe("Schema object columns for list view", () => {
  it("should return correct attribute columns", () => {
    const calculatedAttributes = getObjectAttributes({ schema: C_deviceSchema, forListView: true });
    expect(calculatedAttributes).toStrictEqual(C_deviceAttributeListColumns);
  });

  it("should return correct relationship columns", () => {
    const calculatedRelationships = getObjectRelationships({
      schema: C_deviceSchema,
      forListView: true,
    });
    expect(calculatedRelationships).toStrictEqual(C_deviceRelationshipColumns);
  });

  it("should return correct object columns", () => {
    const calculatedObjectColumns = getSchemaObjectColumns({
      schema: C_deviceSchema,
      forListView: true,
    });
    expect(calculatedObjectColumns).toStrictEqual(C_deviceObjectColumns);
  });
});

describe("Schema object columns for profiles", () => {
  it("should return correct columns", () => {
    const calculatedAttributes = getObjectAttributes({ schema: C_deviceSchema, forProfiles: true });
    expect(calculatedAttributes).toStrictEqual(C_deviceProfileColumns);
  });
});
