import { describe, expect, it } from "vitest";

import { generateAttributeSchema } from "../../../../../tests/fake/schema";
import { canNumberPoolAllocateTo } from "./can-number-pool-allocate-to";

describe("canNumberPoolAllocateTo", () => {
  it("accepts a number attribute that is not read-only", () => {
    // GIVEN
    const attribute = generateAttributeSchema({ name: "vlan_id", kind: "Number" });

    // WHEN
    const result = canNumberPoolAllocateTo(attribute);

    // THEN
    expect(result).toBe(true);
  });

  it("refuses a read-only number attribute, because its value is computed", () => {
    // GIVEN
    const attribute = generateAttributeSchema({ name: "vlan_id", kind: "Number", read_only: true });

    // WHEN
    const result = canNumberPoolAllocateTo(attribute);

    // THEN
    expect(result).toBe(false);
  });

  it("refuses an attribute that does not hold a number", () => {
    // GIVEN
    const attribute = generateAttributeSchema({ name: "name", kind: "Text" });

    // WHEN
    const result = canNumberPoolAllocateTo(attribute);

    // THEN
    expect(result).toBe(false);
  });
});
