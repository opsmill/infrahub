import { describe, expect, it } from "vitest";

import type { IpPoolUtilizationNode } from "@/entities/resource-manager/api/get-ip-pool-utilization-from-api";

import { mapToIpPoolUtilization } from "./ip-pool-utilization.mappers";

const node: IpPoolUtilizationNode = {
  count: 2,
  utilization: 45.5,
  utilization_default_branch: 40,
  utilization_branches: 5.5,
  edges: [
    {
      node: {
        id: "r1",
        display_label: "10.0.0.0/16",
        kind: "IpamIPPrefix",
        utilization: 91,
        utilization_default_branch: 84,
        utilization_branches: 7,
      },
    },
    {
      node: {
        id: "r2",
        display_label: "10.1.0.0/16",
        kind: "IpamIPPrefix",
        utilization: 0,
        utilization_default_branch: 0,
        utilization_branches: 0,
      },
    },
  ],
};

describe("mapToIpPoolUtilization", () => {
  it("maps the pool usage and each resource prefix with its weight", () => {
    // GIVEN
    const weightsById = new Map([["r1", 100]]);

    // WHEN
    const utilization = mapToIpPoolUtilization(node, weightsById);

    // THEN
    expect(utilization).toEqual({
      usage: { utilization: 45.5, utilizationDefaultBranch: 40, utilizationBranches: 5.5 },
      resources: [
        {
          id: "r1",
          __typename: "IpamIPPrefix",
          display_label: "10.0.0.0/16",
          allocationWeight: 100,
          usage: { utilization: 91, utilizationDefaultBranch: 84, utilizationBranches: 7 },
        },
        {
          id: "r2",
          __typename: "IpamIPPrefix",
          display_label: "10.1.0.0/16",
          allocationWeight: null,
          usage: { utilization: 0, utilizationDefaultBranch: 0, utilizationBranches: 0 },
        },
      ],
    });
  });
});
