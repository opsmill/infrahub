import { describe, expect, it } from "vitest";

import { getSchemaIcon } from "@/entities/schema/utils/get-schema-icon";

import { generateNodeSchema } from "../../../../tests/fake/schema";

describe("getSchemaIcon", () => {
  it("should return default icon when schema is null", () => {
    // GIVEN
    const schema = null;

    // WHEN
    const result = getSchemaIcon(schema);

    // THEN
    expect(result).toBe("mdi:cube-outline");
  });

  it("should return default icon when schema is undefined", () => {
    // GIVEN
    const schema = undefined;

    // WHEN
    const result = getSchemaIcon(schema);

    // THEN
    expect(result).toBe("mdi:cube-outline");
  });

  it("should return default icon when schema has no icon property", () => {
    // GIVEN
    const schema = generateNodeSchema({ icon: undefined });

    // WHEN
    const result = getSchemaIcon(schema);

    // THEN
    expect(result).toBe("mdi:cube-outline");
  });

  it("should return schema icon when it exists", () => {
    // GIVEN
    const schema = generateNodeSchema({ icon: "mdi:icon" });

    // WHEN
    const result = getSchemaIcon(schema);

    // THEN
    expect(result).toBe("mdi:icon");
  });
});
