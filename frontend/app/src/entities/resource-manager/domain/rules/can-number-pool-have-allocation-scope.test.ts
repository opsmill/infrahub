import { describe, expect, it } from "vitest";

import { generateAttributeSchema } from "../../../../../tests/fake/schema";
import { canNumberPoolHaveAllocationScope } from "./can-number-pool-have-allocation-scope";

describe("canNumberPoolHaveAllocationScope", () => {
  it("accepts an allocation scope for an attribute that is not unique", () => {
    // GIVEN
    const attribute = generateAttributeSchema({ name: "unit_id", kind: "Number", unique: false });

    // WHEN
    const result = canNumberPoolHaveAllocationScope(attribute);

    // THEN
    expect(result).toBe(true);
  });

  it("refuses an allocation scope for a unique attribute, because its numbers form one sequence", () => {
    // GIVEN
    const attribute = generateAttributeSchema({ name: "vlan_id", kind: "Number", unique: true });

    // WHEN
    const result = canNumberPoolHaveAllocationScope(attribute);

    // THEN
    expect(result).toBe(false);
  });
});
