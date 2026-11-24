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

const prefixPoolNode = {
  id: "pool-id",
  hfid: ["Fabric links"],
  display_label: "Fabric links",
  __typename: "CoreIPPrefixPool",
  name: { value: "Fabric links" },
  description: { value: "Point-to-point links" },
  default_prefix_length: { value: 31 },
  default_prefix_type: { value: "IpamIPPrefix" },
  default_member_type: { value: "address" },
  ip_namespace: { node: { id: "ns-id", display_label: "default", default: { value: true } } },
};

describe("getIpPool", () => {
  afterEach(() => {
    vi.resetAllMocks();
  });

  it("returns the prefix pool when the prefix pool query finds it", async () => {
    // GIVEN
    vi.mocked(getIpPoolFromApi).mockResolvedValue({
      data: {
        CoreIPPrefixPool: { edges: [{ node: prefixPoolNode }] },
        CoreIPAddressPool: { edges: [] },
      },
    } as unknown as ApiResult);

    // WHEN
    const pool = await getIpPool(params);

    // THEN
    expect(getIpPoolFromApi).toHaveBeenCalledWith(params);
    expect(pool).toEqual({
      id: "pool-id",
      hfid: ["Fabric links"],
      display_label: "Fabric links",
      __typename: "CoreIPPrefixPool",
      name: { value: "Fabric links" },
      description: { value: "Point-to-point links" },
      default_prefix_length: { value: 31 },
      default_prefix_type: { value: "IpamIPPrefix" },
      default_member_type: { value: "address" },
      ip_namespace: { id: "ns-id", display_label: "default", isDefault: true },
    });
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
    expect(getIpPoolFromApi).toHaveBeenCalledWith(params);
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
