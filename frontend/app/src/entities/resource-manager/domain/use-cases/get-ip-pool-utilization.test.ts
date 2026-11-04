import { afterEach, describe, expect, it, vi } from "vitest";

import { getIpPoolResourceWeightsFromApi } from "@/entities/resource-manager/api/get-ip-pool-resource-weights-from-api";
import { getIpPoolUtilizationFromApi } from "@/entities/resource-manager/api/get-ip-pool-utilization-from-api";

import { getIpPoolUtilization } from "./get-ip-pool-utilization";

vi.mock("@/entities/resource-manager/api/get-ip-pool-utilization-from-api", () => ({
  getIpPoolUtilizationFromApi: vi.fn(),
}));

vi.mock("@/entities/resource-manager/api/get-ip-pool-resource-weights-from-api", () => ({
  getIpPoolResourceWeightsFromApi: vi.fn(),
}));

type UtilizationResult = Awaited<ReturnType<typeof getIpPoolUtilizationFromApi>>;
type WeightsResult = Awaited<ReturnType<typeof getIpPoolResourceWeightsFromApi>>;

const context = { branchName: "main", atDate: null };

const figures = { utilization: 10, utilization_default_branch: 10, utilization_branches: 0 };

const utilizationData = {
  InfrahubResourcePoolUtilization: {
    count: 2,
    ...figures,
    edges: [
      { node: { id: "r-b", display_label: "10.1.0.0/16", kind: "IpamIPPrefix", ...figures } },
      { node: { id: "r-a", display_label: "10.0.0.0/16", kind: "IpamIPPrefix", ...figures } },
    ],
  },
};

describe("getIpPoolUtilization", () => {
  afterEach(() => {
    vi.resetAllMocks();
  });

  it("orders the resource prefixes without asking for weights when no prefix kind has one", async () => {
    // GIVEN
    vi.mocked(getIpPoolUtilizationFromApi).mockResolvedValue({
      data: utilizationData,
    } as unknown as UtilizationResult);

    // WHEN
    const utilization = await getIpPoolUtilization({
      poolId: "pool",
      weightedKinds: [],
      ...context,
    });

    // THEN
    expect(getIpPoolResourceWeightsFromApi).not.toHaveBeenCalled();
    expect(utilization.resources.map(({ id, allocationWeight }) => [id, allocationWeight])).toEqual(
      [
        ["r-a", null],
        ["r-b", null],
      ]
    );
  });

  it("reads the weights of the resource prefixes and orders by them", async () => {
    // GIVEN
    vi.mocked(getIpPoolUtilizationFromApi).mockResolvedValue({
      data: utilizationData,
    } as unknown as UtilizationResult);
    vi.mocked(getIpPoolResourceWeightsFromApi).mockResolvedValue({
      data: {
        BuiltinIPPrefix: {
          edges: [
            { node: { id: "r-a", allocation_weight: { value: 10 } } },
            { node: { id: "r-b", allocation_weight: { value: 100 } } },
          ],
        },
      },
    } as unknown as WeightsResult);

    // WHEN
    const utilization = await getIpPoolUtilization({
      poolId: "pool",
      weightedKinds: ["IpamIPPrefix"],
      ...context,
    });

    // THEN
    expect(getIpPoolResourceWeightsFromApi).toHaveBeenCalledWith({
      resourceIds: ["r-b", "r-a"],
      weightedKinds: ["IpamIPPrefix"],
      ...context,
    });
    expect(utilization.resources.map(({ id, allocationWeight }) => [id, allocationWeight])).toEqual(
      [
        ["r-b", 100],
        ["r-a", 10],
      ]
    );
  });

  it("throws the API errors", async () => {
    // GIVEN
    vi.mocked(getIpPoolUtilizationFromApi).mockResolvedValue({
      data: undefined,
      errors: [{ message: "first" }, { message: "second" }],
    } as unknown as UtilizationResult);

    // WHEN
    const result = getIpPoolUtilization({ poolId: "pool", weightedKinds: [], ...context });

    // THEN
    await expect(result).rejects.toThrow("first; second");
  });
});
