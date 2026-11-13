import { describe, expect, it } from "vitest";

import type { IpPoolAllocationsNode } from "@/entities/resource-manager/api/get-ip-pool-allocations-from-api";

import { mapToIpPoolAllocationsPage } from "./ip-pool-allocation.mappers";

describe("mapToIpPoolAllocationsPage", () => {
  it("maps the count and each allocation, with an empty identifier as null", () => {
    // GIVEN
    const node = {
      count: "2",
      edges: [
        {
          node: {
            id: "a1",
            display_label: "10.0.0.1/32",
            kind: "IpamIPAddress",
            identifier: "atl1-edge1",
          },
        },
        {
          node: { id: "a2", display_label: "10.0.0.2/32", kind: "IpamIPAddress", identifier: null },
        },
      ],
    } as unknown as IpPoolAllocationsNode;

    // WHEN
    const page = mapToIpPoolAllocationsPage(node);

    // THEN
    expect(page).toEqual({
      count: 2,
      allocations: [
        {
          id: "a1",
          __typename: "IpamIPAddress",
          display_label: "10.0.0.1/32",
          identifier: "atl1-edge1",
        },
        { id: "a2", __typename: "IpamIPAddress", display_label: "10.0.0.2/32", identifier: null },
      ],
    });
  });
});
