import { describe, expect, it } from "vitest";

import type { NumberPoolUtilizationNode } from "./get-number-pool-utilization-from-api";
import { mapToNumberPoolUtilization } from "./number-pool-utilization.mappers";

const figures = (used: number, size: number) => ({
  size,
  used,
  used_default_branch: used,
  used_branches: 0,
  utilization: 0,
});

describe("mapToNumberPoolUtilization", () => {
  it("maps the pool and range figures", () => {
    // GIVEN
    const node = {
      figures: { size: 100, used: 30, used_default_branch: 28, used_branches: 2, utilization: 30 },
      ranges: [{ id: "range-1", start: 1, end: 50, weight: 10, figures: figures(30, 50) }],
    } as NumberPoolUtilizationNode;

    // WHEN
    const utilization = mapToNumberPoolUtilization(node);

    // THEN
    expect(utilization).toEqual({
      usage: { size: 100, used: 30, usedDefaultBranch: 28, usedBranches: 2, utilization: 30 },
      ranges: [
        {
          id: "range-1",
          __typename: "CoreNumberPoolRange",
          start: { value: 1 },
          end: { value: 50 },
          allocation_weight: { value: 10 },
          usage: { size: 50, used: 30, usedDefaultBranch: 30, usedBranches: 0, utilization: 0 },
        },
      ],
    });
  });
});
