import { describe, expect, it } from "vitest";

import type { NumberPoolAllocationNode } from "./get-number-pool-allocations-from-api";
import { mapToNumberPoolAllocation } from "./number-pool-allocation.mappers";

const buildNode = (overrides: Partial<Record<keyof NumberPoolAllocationNode, unknown>> = {}) =>
  ({
    value: "64512",
    branch: "b1",
    provenance: "ALLOCATED",
    holder: { id: "device-1", kind: "InfraDevice", display_label: "leaf-par1-01" },
    range: { id: "range-1" },
    ...overrides,
  }) as NumberPoolAllocationNode;

describe("mapToNumberPoolAllocation", () => {
  it("maps the number, its holder and its range", () => {
    // WHEN
    const allocation = mapToNumberPoolAllocation(buildNode());

    // THEN
    expect(allocation).toEqual({
      value: 64_512,
      branch: "b1",
      holder: { id: "device-1", __typename: "InfraDevice", display_label: "leaf-par1-01" },
      provenance: "ALLOCATED",
      rangeId: "range-1",
    });
  });

  it("keeps a number a user provided", () => {
    // WHEN
    const allocation = mapToNumberPoolAllocation(buildNode({ provenance: "PROVIDED" }));

    // THEN
    expect(allocation.provenance).toBe("PROVIDED");
  });
});
