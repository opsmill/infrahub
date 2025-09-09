import { describe, expect, it } from "vitest";

import { isGenericSchema } from "@/entities/schema/utils/is-generic-schema";

import { generateGenericSchema, generateNodeSchema } from "../../../../tests/fake/schema";

describe("isGenericSchema", () => {
  it("should return true for a generic schema", () => {
    // GIVEN
    const schema = generateGenericSchema();

    // WHEN
    const result = isGenericSchema(schema);

    // THEN
    expect(result).toBe(true);
  });

  it("should return false for a non-generic schema", () => {
    // GIVEN
    const schema = generateNodeSchema();

    // WHEN
    const result = isGenericSchema(schema);

    // THEN
    expect(result).toBe(false);
  });
});
