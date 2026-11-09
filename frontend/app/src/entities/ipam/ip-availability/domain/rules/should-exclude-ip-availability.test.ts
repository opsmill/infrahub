import { describe, expect, it } from "vitest";

import { AVAILABLE_IP_FILTER_NAME } from "@/entities/ipam/ip-availability/domain/model/ip-availability-filter";
import { shouldExcludeIpAvailability } from "@/entities/ipam/ip-availability/domain/rules/should-exclude-ip-availability";
import type { Filter } from "@/entities/nodes/filters/domain/model/filter";
import type { Sort } from "@/entities/nodes/sort/domain/model/sort";

describe("shouldExcludeIpAvailability", () => {
  it("keeps available IPs on the default order (no custom sort, compatible filters)", () => {
    // GIVEN
    const parentScope: Filter[] = [{ name: "parent__ids", value: [{ id: "p1" }] }];
    const sort: Sort[] | null = null;

    // WHEN
    const result = shouldExcludeIpAvailability(parentScope, sort);

    // THEN
    expect(result).toBe(false);
  });

  it("excludes available IPs once a custom sort is applied", () => {
    // GIVEN
    const parentScope: Filter[] = [{ name: "parent__ids", value: [{ id: "p1" }] }];
    const sort: Sort[] = [{ field: "prefix__version", direction: "DESC" }];

    // WHEN
    const result = shouldExcludeIpAvailability(parentScope, sort);

    // THEN
    expect(result).toBe(true);
  });

  it("excludes available IPs when an incompatible filter is present", () => {
    // GIVEN
    const filters: Filter[] = [{ name: "description__value", value: "x" }];

    // WHEN
    const result = shouldExcludeIpAvailability(filters, null);

    // THEN
    expect(result).toBe(true);
  });

  it("treats an empty sort array like no sort", () => {
    // GIVEN
    const filters: Filter[] = [{ name: AVAILABLE_IP_FILTER_NAME, value: true }];

    // WHEN
    const result = shouldExcludeIpAvailability(filters, []);

    // THEN
    expect(result).toBe(false);
  });
});
