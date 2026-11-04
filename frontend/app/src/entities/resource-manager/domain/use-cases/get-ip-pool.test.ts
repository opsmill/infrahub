import { afterEach, describe, expect, it, vi } from "vitest";

import { getIpPoolFromApi } from "@/entities/resource-manager/api/get-ip-pool-from-api";

import { getIpPool } from "./get-ip-pool";

vi.mock("@/entities/resource-manager/api/get-ip-pool-from-api", () => ({
  getIpPoolFromApi: vi.fn(),
}));

type ApiResult = Awaited<ReturnType<typeof getIpPoolFromApi>>;

const params = { poolId: "pool-id", branchName: "main", atDate: null };

const addressPoolNode = {
  id: "pool-id",
  hfid: ["Loopbacks"],
  display_label: "Loopbacks",
  __typename: "CoreIPAddressPool",
  name: { value: "Loopbacks" },
  description: { value: null },
  default_prefix_length: { value: 32 },
  default_address_type: { value: "IpamIPAddress" },
  ip_namespace: { node: { id: "ns-id", display_label: "default", default: { value: true } } },
};

describe("getIpPool", () => {
  afterEach(() => {
    vi.resetAllMocks();
  });

  it("returns the address pool when the prefix pool query finds nothing", async () => {
    // GIVEN
    vi.mocked(getIpPoolFromApi).mockResolvedValue({
      data: {
        CoreIPPrefixPool: { edges: [] },
        CoreIPAddressPool: { edges: [{ node: addressPoolNode }] },
      },
    } as unknown as ApiResult);

    // WHEN
    const pool = await getIpPool(params);

    // THEN
    expect(pool).toEqual({
      id: "pool-id",
      hfid: ["Loopbacks"],
      display_label: "Loopbacks",
      __typename: "CoreIPAddressPool",
      name: { value: "Loopbacks" },
      description: { value: null },
      default_prefix_length: { value: 32 },
      default_address_type: { value: "IpamIPAddress" },
      ip_namespace: { id: "ns-id", display_label: "default", isDefault: true },
    });
  });

  it("throws the API errors", async () => {
    // GIVEN
    vi.mocked(getIpPoolFromApi).mockResolvedValue({
      data: undefined,
      errors: [{ message: "first" }, { message: "second" }],
    } as unknown as ApiResult);

    // WHEN
    const result = getIpPool(params);

    // THEN
    await expect(result).rejects.toThrow("first; second");
  });

  it("throws when neither query finds the pool", async () => {
    // GIVEN
    vi.mocked(getIpPoolFromApi).mockResolvedValue({
      data: { CoreIPPrefixPool: { edges: [] }, CoreIPAddressPool: { edges: [] } },
    } as unknown as ApiResult);

    // WHEN
    const result = getIpPool(params);

    // THEN
    await expect(result).rejects.toThrow("IP pool not found");
  });
});
