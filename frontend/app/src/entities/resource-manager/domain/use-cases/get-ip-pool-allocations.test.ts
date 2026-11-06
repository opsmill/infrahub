import { afterEach, describe, expect, it, vi } from "vitest";

import { getIpPoolAllocationsFromApi } from "@/entities/resource-manager/api/get-ip-pool-allocations-from-api";

import { getIpPoolAllocations } from "./get-ip-pool-allocations";

vi.mock("@/entities/resource-manager/api/get-ip-pool-allocations-from-api", () => ({
  getIpPoolAllocationsFromApi: vi.fn(),
}));

type ApiResult = Awaited<ReturnType<typeof getIpPoolAllocationsFromApi>>;

const params = {
  poolId: "pool-id",
  resourceId: "resource-id",
  offset: 100,
  limit: 100,
  branchName: "branch-1",
  atDate: new Date("2026-01-01T00:00:00Z"),
};

describe("getIpPoolAllocations", () => {
  afterEach(() => {
    vi.resetAllMocks();
  });

  it("returns the page of allocated prefixes", async () => {
    // GIVEN
    vi.mocked(getIpPoolAllocationsFromApi).mockResolvedValue({
      data: {
        InfrahubResourcePoolAllocated: {
          count: 1,
          edges: [
            {
              node: {
                id: "prefix-1",
                display_label: "10.0.0.0/31",
                kind: "IpamIPPrefix",
                identifier: "leaf-01",
              },
            },
          ],
        },
      },
    } as unknown as ApiResult);

    // WHEN
    const result = await getIpPoolAllocations(params);

    // THEN
    expect(result).toEqual({
      count: 1,
      allocations: [
        {
          id: "prefix-1",
          __typename: "IpamIPPrefix",
          display_label: "10.0.0.0/31",
          identifier: "leaf-01",
        },
      ],
    });
  });

  it("sends the branch, the date and the page bounds to the API", async () => {
    // GIVEN
    vi.mocked(getIpPoolAllocationsFromApi).mockResolvedValue({
      data: { InfrahubResourcePoolAllocated: { count: 0, edges: [] } },
    } as unknown as ApiResult);

    // WHEN
    await getIpPoolAllocations(params);

    // THEN
    expect(getIpPoolAllocationsFromApi).toHaveBeenCalledWith(params);
  });
});
