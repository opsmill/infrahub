import { describe, expect, it } from "vitest";

import { isNodeSchema } from "@/entities/schema/utils/is-node-schema";

import { generateGenericSchema, generateNodeSchema } from "../../../../tests/fake/schema";

describe("isNodeSchema", () => {
  it("should return true for a node schema", () => {
    // GIVEN
    const schema = generateNodeSchema();

    // WHEN
    const result = isNodeSchema(schema);

    // THEN
    expect(result).toBe(true);
  });

  it("should return false for a non-node schema", () => {
    // GIVEN
    const schema = generateGenericSchema();

    // WHEN
    const result = isNodeSchema(schema);

    // THEN
    expect(result).toBe(false);
  });
});
