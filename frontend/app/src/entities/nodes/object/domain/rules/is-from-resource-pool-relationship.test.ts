import { describe, expect, it } from "vitest";

import { isFromResourcePoolRelationship } from "./is-from-resource-pool-relationship";

describe("isFromResourcePoolRelationship", () => {
  it("should return true for names ending with _from_resource_pool", () => {
    // GIVEN
    const name = "primary_address_from_resource_pool";

    // WHEN
    const result = isFromResourcePoolRelationship(name);

    // THEN
    expect(result).toBe(true);
  });

  it("should return false for regular relationship names", () => {
    // GIVEN
    const name = "primary_address";

    // WHEN
    const result = isFromResourcePoolRelationship(name);

    // THEN
    expect(result).toBe(false);
  });

  it("should return false for names containing but not ending with _from_resource_pool", () => {
    // GIVEN
    const name = "_from_resource_pool_extra";

    // WHEN
    const result = isFromResourcePoolRelationship(name);

    // THEN
    expect(result).toBe(false);
  });
});
