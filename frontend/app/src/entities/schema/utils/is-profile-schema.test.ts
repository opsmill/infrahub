import { describe, expect, it } from "vitest";

import { isProfileSchema } from "@/entities/schema/utils/is-profile-schema";

import { generateNodeSchema, generateProfileSchema } from "../../../../tests/fake/schema";

describe("isProfileSchema", () => {
  it("should return true for a profile schema", () => {
    // GIVEN
    const schema = generateProfileSchema({ namespace: "Profile" });

    // WHEN
    const result = isProfileSchema(schema);

    // THEN
    expect(result).toBe(true);
  });

  it("should return false for a non-profile schema", () => {
    // GIVEN
    const schema = generateNodeSchema({ namespace: "Other" });

    // WHEN
    const result = isProfileSchema(schema);

    // THEN
    expect(result).toBe(false);
  });
});
