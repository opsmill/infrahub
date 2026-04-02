import { describe, expect, it } from "vitest";

import { AVAILABLE_IP_FILTER_NAME } from "@/entities/ipam/constants";
import { getFilterCount } from "@/entities/nodes/object/ui/filters/filter-menu";
import type { Filter } from "@/shared/hooks/useFilters";

import { generateNodeSchema } from "../../../../../../tests/fake/schema";

describe("getFilterCount", () => {
  it("returns the number of filters for a non-IPAM schema", () => {
    // GIVEN
    const schema = generateNodeSchema({ kind: "InfraDevice" });
    const filters: Filter[] = [
      { name: "name__value", value: "test" },
      { name: "status__value", value: "active" },
    ];

    // WHEN
    const result = getFilterCount(schema, filters);

    // THEN
    expect(result).toBe(2);
  });

  it("adds 1 for an IPAM schema without an explicit availability filter", () => {
    // GIVEN
    const schema = generateNodeSchema({
      kind: "IpamIPPrefix",
      inherit_from: ["BuiltinIPPrefix"],
    });
    const filters: Filter[] = [{ name: "parent__ids", value: ["some-id"] }];

    // WHEN
    const result = getFilterCount(schema, filters);

    // THEN
    expect(result).toBe(2);
  });

  it("subtracts 1 for an IPAM schema with availability filter set to false", () => {
    // GIVEN
    const schema = generateNodeSchema({
      kind: "IpamIPPrefix",
      inherit_from: ["BuiltinIPPrefix"],
    });
    const filters: Filter[] = [{ name: AVAILABLE_IP_FILTER_NAME, value: false }];

    // WHEN
    const result = getFilterCount(schema, filters);

    // THEN
    expect(result).toBe(0);
  });

  it("returns the exact count for an IPAM schema with availability filter set to true", () => {
    // GIVEN
    const schema = generateNodeSchema({
      kind: "IpamIPPrefix",
      inherit_from: ["BuiltinIPPrefix"],
    });
    const filters: Filter[] = [{ name: AVAILABLE_IP_FILTER_NAME, value: true }];

    // WHEN
    const result = getFilterCount(schema, filters);

    // THEN
    expect(result).toBe(1);
  });

  it("returns regular count for an IPAM schema with incompatible filters", () => {
    // GIVEN
    const schema = generateNodeSchema({
      kind: "IpamIPPrefix",
      inherit_from: ["BuiltinIPPrefix"],
    });
    const filters: Filter[] = [
      { name: "name__value", value: "test" },
      { name: "status__value", value: "active" },
    ];

    // WHEN
    const result = getFilterCount(schema, filters);

    // THEN
    expect(result).toBe(2);
  });
});
