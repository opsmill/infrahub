import { afterEach, describe, expect, it, vi } from "vitest";

import { getNumberPoolFromApi } from "@/entities/resource-manager/api/get-number-pool-from-api";

import { getNumberPool } from "./get-number-pool";

vi.mock("@/entities/resource-manager/api/get-number-pool-from-api", () => ({
  getNumberPoolFromApi: vi.fn(),
}));

type ApiResult = Awaited<ReturnType<typeof getNumberPoolFromApi>>;

const params = { poolId: "pool-id", branchName: "main", atDate: null };

const poolNode = {
  id: "pool-id",
  hfid: ["Interface speeds"],
  display_label: "Interface speeds",
  __typename: "CoreNumberPool",
  name: { value: "Interface speeds" },
  description: { value: null },
  pool_type: { value: "Schema" },
  node: { value: "InfraInterface" },
  node_attribute: { value: "speed" },
  allocation_scope: { value: ["device"] },
};

describe("getNumberPool", () => {
  afterEach(() => {
    vi.resetAllMocks();
  });

  it("returns the pool in its domain shape", async () => {
    // GIVEN
    vi.mocked(getNumberPoolFromApi).mockResolvedValue({
      data: {
        CoreNumberPool: { edges: [{ node: { ...poolNode, allocation_scope: { value: null } } }] },
      },
    } as unknown as ApiResult);

    // WHEN
    const pool = await getNumberPool(params);

    // THEN
    expect(pool).toEqual({
      id: "pool-id",
      hfid: ["Interface speeds"],
      display_label: "Interface speeds",
      __typename: "CoreNumberPool",
      name: { value: "Interface speeds" },
      description: { value: null },
      pool_type: { value: "Schema" },
      node: { value: "InfraInterface" },
      node_attribute: { value: "speed" },
      allocation_scope: { value: [] },
    });
  });

  it("throws the API errors", async () => {
    // GIVEN
    vi.mocked(getNumberPoolFromApi).mockResolvedValue({
      data: undefined,
      errors: [{ message: "first" }, { message: "second" }],
    } as unknown as ApiResult);

    // WHEN
    const result = getNumberPool(params);

    // THEN
    await expect(result).rejects.toThrow("first; second");
  });

  it("throws when the pool does not exist", async () => {
    // GIVEN
    vi.mocked(getNumberPoolFromApi).mockResolvedValue({
      data: { CoreNumberPool: { edges: [] } },
    } as unknown as ApiResult);

    // WHEN
    const result = getNumberPool(params);

    // THEN
    await expect(result).rejects.toThrow("Number pool not found");
  });
});
