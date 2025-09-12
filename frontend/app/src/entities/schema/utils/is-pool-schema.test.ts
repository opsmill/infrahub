import { describe, expect, it } from "vitest";

import { RESOURCE_GENERIC_KIND } from "@/entities/resource-manager/constants";
import { isPoolSchema } from "@/entities/schema/utils/is-pool-schema";

import { generateGenericSchema, generateNodeSchema } from "../../../../tests/fake/schema";

describe("isPoolSchema", () => {
  it("should return true for a schema that inherits from resource generic kind", () => {
    // GIVEN
    const schema = generateNodeSchema({ inherit_from: [RESOURCE_GENERIC_KIND] });

    // WHEN
    const result = isPoolSchema(schema);

    // THEN
    expect(result).toBe(true);
  });

  it("should return true for a schema that inherits from multiple kinds including resource generic kind", () => {
    // GIVEN
    const schema = generateNodeSchema({ inherit_from: ["SomeOtherKind", RESOURCE_GENERIC_KIND] });

    // WHEN
    const result = isPoolSchema(schema);

    // THEN
    expect(result).toBe(true);
  });

  it("should return false for a schema that does not inherit from resource generic kind", () => {
    // GIVEN
    const schema = generateNodeSchema({ inherit_from: ["SomeOtherKind"] });

    // WHEN
    const result = isPoolSchema(schema);

    // THEN
    expect(result).toBe(false);
  });

  it("should return false for a schema with undefined inherit_from", () => {
    // GIVEN
    const schema = generateNodeSchema({ inherit_from: undefined });

    // WHEN
    const result = isPoolSchema(schema);

    // THEN
    expect(result).toBe(false);
  });

  it("should return false for a schema with empty inherit_from array", () => {
    // GIVEN
    const schema = generateNodeSchema({ inherit_from: [] });

    // WHEN
    const result = isPoolSchema(schema);

    // THEN
    expect(result).toBe(false);
  });

  it("should return false for a generic schema even if it inherits from resource generic kind", () => {
    // GIVEN
    const schema = generateGenericSchema();

    // WHEN
    const result = isPoolSchema(schema);

    // THEN
    expect(result).toBe(false);
  });
});
