import { afterEach, describe, expect, it, vi } from "vitest";

import { getIpAddressPoolFromApi } from "@/entities/resource-manager/api/get-ip-address-pool-from-api";
import { getIpPrefixPoolFromApi } from "@/entities/resource-manager/api/get-ip-prefix-pool-from-api";
import { IP_ADDRESS_POOL, IP_PREFIX_POOL } from "@/entities/resource-manager/domain/model/pool";

import { getIpPool } from "./get-ip-pool";

vi.mock("@/entities/resource-manager/api/get-ip-prefix-pool-from-api", () => ({
  getIpPrefixPoolFromApi: vi.fn(),
}));

vi.mock("@/entities/resource-manager/api/get-ip-address-pool-from-api", () => ({
  getIpAddressPoolFromApi: vi.fn(),
}));

type PrefixPoolResult = Awaited<ReturnType<typeof getIpPrefixPoolFromApi>>;
type AddressPoolResult = Awaited<ReturnType<typeof getIpAddressPoolFromApi>>;

const context = { poolId: "pool-id", branchName: "main", atDate: null };

const namespaceNode = { id: "ns-id", display_label: "default", default: { value: true } };

const prefixPoolNode = {
  id: "pool-id",
  hfid: ["Links"],
  display_label: "Links",
  __typename: "CoreIPPrefixPool",
  name: { value: "Links" },
  description: { value: null },
  default_prefix_length: { value: 31 },
  default_prefix_type: { value: "IpamIPPrefix" },
  default_member_type: { value: "address" },
  ip_namespace: { node: namespaceNode },
};

const addressPoolNode = {
  id: "pool-id",
  hfid: ["Loopbacks"],
  display_label: "Loopbacks",
  __typename: "CoreIPAddressPool",
  name: { value: "Loopbacks" },
  description: { value: null },
  default_prefix_length: { value: 32 },
  default_address_type: { value: "IpamIPAddress" },
  ip_namespace: { node: namespaceNode },
};

describe("getIpPool", () => {
  afterEach(() => {
    vi.resetAllMocks();
  });

  it("reads a prefix pool with the prefix pool query only", async () => {
    // GIVEN
    vi.mocked(getIpPrefixPoolFromApi).mockResolvedValue({
      data: { CoreIPPrefixPool: { edges: [{ node: prefixPoolNode }] } },
    } as unknown as PrefixPoolResult);

    // WHEN
    const pool = await getIpPool({ ...context, poolKind: IP_PREFIX_POOL });

    // THEN
    expect(getIpPrefixPoolFromApi).toHaveBeenCalledWith(context);
    expect(getIpAddressPoolFromApi).not.toHaveBeenCalled();
    expect(pool).toEqual({
      id: "pool-id",
      hfid: ["Links"],
      display_label: "Links",
      __typename: "CoreIPPrefixPool",
      name: { value: "Links" },
      description: { value: null },
      default_prefix_length: { value: 31 },
      default_prefix_type: { value: "IpamIPPrefix" },
      default_member_type: { value: "address" },
      ip_namespace: { id: "ns-id", display_label: "default", isDefault: true },
    });
  });

  it("reads an address pool with the address pool query only", async () => {
    // GIVEN
    vi.mocked(getIpAddressPoolFromApi).mockResolvedValue({
      data: { CoreIPAddressPool: { edges: [{ node: addressPoolNode }] } },
    } as unknown as AddressPoolResult);

    // WHEN
    const pool = await getIpPool({ ...context, poolKind: IP_ADDRESS_POOL });

    // THEN
    expect(getIpAddressPoolFromApi).toHaveBeenCalledWith(context);
    expect(getIpPrefixPoolFromApi).not.toHaveBeenCalled();
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

  it("throws when the pool is not of the given kind", async () => {
    // GIVEN
    vi.mocked(getIpPrefixPoolFromApi).mockResolvedValue({
      data: { CoreIPPrefixPool: { edges: [] } },
    } as unknown as PrefixPoolResult);

    // WHEN
    const result = getIpPool({ ...context, poolKind: IP_PREFIX_POOL });

    // THEN
    await expect(result).rejects.toThrow("IP pool not found");
  });
});
