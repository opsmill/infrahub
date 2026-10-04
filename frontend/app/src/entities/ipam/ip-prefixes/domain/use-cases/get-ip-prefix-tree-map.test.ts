import { beforeEach, describe, expect, it, vi } from "vitest";

import { getIpPrefixTreeMap } from "@/entities/ipam/ip-prefixes/domain/use-cases/get-ip-prefix-tree-map";

const getIpPrefixTreeMapFromApi = vi.hoisted(() => vi.fn());

vi.mock("@/entities/ipam/ip-prefixes/api/get-ip-prefix-tree-map-from-api", () => ({
  getIpPrefixTreeMapFromApi,
}));

const PARAMS = { parentId: "parent-id", limit: 1000, branchName: "main", atDate: null };

const ADDRESS_CHILD = {
  __typename: "IpamIPPrefix",
  id: "1808d317-21bb-8bdf-d0ec-c51b636fbbeb",
  display_label: "10.0.0.0/16",
  prefix: { value: "10.0.0.0/16" },
  member_type: { value: "address" },
  is_pool: { value: false },
  utilization: { value: 0 },
  description: { value: null },
  children: { count: 0 },
  ip_addresses: { count: 30 },
};

const PREFIX_CHILD_WITH_CHILDREN = {
  __typename: "IpamIPPrefix",
  id: "1808d318-bc0d-b958-d0e1-c511b808cac8",
  display_label: "10.1.0.0/16",
  prefix: { value: "10.1.0.0/16" },
  member_type: { value: "prefix" },
  is_pool: { value: true },
  utilization: { value: 0 },
  description: { value: null },
  children: { count: 16 },
  ip_addresses: { count: 0 },
};

const PREFIX_CHILD_EMPTY = {
  __typename: "IpamIPPrefix",
  id: "1808d319-1fe0-d6ae-d0ea-c51f768a4cd7",
  display_label: "10.2.0.0/16",
  prefix: { value: "10.2.0.0/16" },
  member_type: { value: "prefix" },
  is_pool: { value: false },
  utilization: { value: 0 },
  description: { value: null },
  children: { count: 0 },
  ip_addresses: { count: 0 },
};

const FREE_BLOCK = {
  __typename: "InternalIPPrefixAvailable",
  id: "18dafbec-c879-c787-11e7-10651a87fdec",
  display_label: "10.3.0.0/16",
  prefix: { value: "10.3.0.0/16" },
  member_type: { value: "address" },
  is_pool: { value: false },
  utilization: { value: null },
  description: { value: null },
  children: { count: 0 },
  ip_addresses: { count: 0 },
};

const SANDBOX_SAMPLE = {
  data: {
    BuiltinIPPrefix: {
      count: 3,
      edges: [
        { node: ADDRESS_CHILD },
        { node: PREFIX_CHILD_WITH_CHILDREN },
        { node: PREFIX_CHILD_EMPTY },
        { node: FREE_BLOCK },
      ],
    },
  },
};

describe("getIpPrefixTreeMap", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("maps real nodes to children in address order with the matching member count", async () => {
    // GIVEN
    getIpPrefixTreeMapFromApi.mockResolvedValue(SANDBOX_SAMPLE);

    // WHEN
    const result = await getIpPrefixTreeMap(PARAMS);

    // THEN
    expect(result.children).toEqual([
      {
        id: ADDRESS_CHILD.id,
        kind: "IpamIPPrefix",
        cidr: "10.0.0.0/16",
        size: { family: "ipv4", prefixLength: 16, addressCount: 65536n },
        memberType: "address",
        isPool: false,
        utilization: 0,
        description: null,
        memberCount: 30,
      },
      {
        id: PREFIX_CHILD_WITH_CHILDREN.id,
        kind: "IpamIPPrefix",
        cidr: "10.1.0.0/16",
        size: { family: "ipv4", prefixLength: 16, addressCount: 65536n },
        memberType: "prefix",
        isPool: true,
        utilization: 0,
        description: null,
        memberCount: 16,
      },
      {
        id: PREFIX_CHILD_EMPTY.id,
        kind: "IpamIPPrefix",
        cidr: "10.2.0.0/16",
        size: { family: "ipv4", prefixLength: 16, addressCount: 65536n },
        memberType: "prefix",
        isPool: false,
        utilization: 0,
        description: null,
        memberCount: 0,
      },
    ]);
  });

  it("maps available nodes to free blocks parsed from their prefix value", async () => {
    // GIVEN
    getIpPrefixTreeMapFromApi.mockResolvedValue(SANDBOX_SAMPLE);

    // WHEN
    const result = await getIpPrefixTreeMap(PARAMS);

    // THEN
    expect(result.freeBlocks).toEqual([
      { cidr: "10.3.0.0/16", size: { family: "ipv4", prefixLength: 16, addressCount: 65536n } },
    ]);
  });

  it("reports the query count as the total child count and is not capped when it matches", async () => {
    // GIVEN
    getIpPrefixTreeMapFromApi.mockResolvedValue(SANDBOX_SAMPLE);

    // WHEN
    const result = await getIpPrefixTreeMap(PARAMS);

    // THEN
    expect({ totalChildCount: result.totalChildCount, isCapped: result.isCapped }).toEqual({
      totalChildCount: 3,
      isCapped: false,
    });
  });

  it("drops a node whose prefix value is null", async () => {
    // GIVEN
    getIpPrefixTreeMapFromApi.mockResolvedValue({
      data: {
        BuiltinIPPrefix: {
          count: 2,
          edges: [
            { node: { ...PREFIX_CHILD_EMPTY, prefix: { value: null } } },
            { node: PREFIX_CHILD_WITH_CHILDREN },
          ],
        },
      },
    });

    // WHEN
    const result = await getIpPrefixTreeMap(PARAMS);

    // THEN
    expect(result.children.map((child) => child.cidr)).toEqual(["10.1.0.0/16"]);
    expect(result.isCapped).toBe(false);
  });

  it("is capped when the count exceeds the real children returned", async () => {
    // GIVEN
    getIpPrefixTreeMapFromApi.mockResolvedValue({
      data: {
        BuiltinIPPrefix: {
          count: 1200,
          edges: [{ node: PREFIX_CHILD_WITH_CHILDREN }, { node: FREE_BLOCK }],
        },
      },
    });

    // WHEN
    const result = await getIpPrefixTreeMap(PARAMS);

    // THEN
    expect(result.isCapped).toBe(true);
  });

  it("passes the parent id, limit, branch and date through to the api", async () => {
    // GIVEN
    getIpPrefixTreeMapFromApi.mockResolvedValue(SANDBOX_SAMPLE);

    // WHEN
    await getIpPrefixTreeMap(PARAMS);

    // THEN
    expect(getIpPrefixTreeMapFromApi).toHaveBeenCalledWith(PARAMS);
  });

  it("rejects with the messages of the errors the api returned", async () => {
    // GIVEN
    getIpPrefixTreeMapFromApi.mockResolvedValue({
      data: null,
      errors: [{ message: "first failure" }, { message: "second failure" }],
    });

    // WHEN
    const call = getIpPrefixTreeMap(PARAMS);

    // THEN
    await expect(call).rejects.toThrow("first failure; second failure");
  });
});
