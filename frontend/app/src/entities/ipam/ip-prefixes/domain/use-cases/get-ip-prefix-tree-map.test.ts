import { afterEach, describe, expect, it, vi } from "vitest";

import { getIpPrefixTreeMap } from "@/entities/ipam/ip-prefixes/domain/use-cases/get-ip-prefix-tree-map";

// An untyped mock keeps the fixtures free of the generated result type, whose typename union
// only knows the core kinds.
const getIpPrefixTreeMapFromApi = vi.hoisted(() => vi.fn());

vi.mock("@/entities/ipam/ip-prefixes/api/get-ip-prefix-tree-map-from-api", () => ({
  getIpPrefixTreeMapFromApi,
}));

const PARAMS = { parentId: "parent-id", limit: 1000, branchName: "main", atDate: null };

const PARENT = {
  __typename: "IpamIPPrefix",
  id: "parent-id",
  prefix: { value: "10.0.0.0/8", prefixlen: 8, version: 4 },
  member_type: { value: "prefix" },
  utilization: { value: 1 },
};

const ADDRESS_CHILD = {
  __typename: "IpamIPPrefix",
  id: "1808d317-21bb-8bdf-d0ec-c51b636fbbeb",
  prefix: { value: "10.0.0.0/16", prefixlen: 16, version: 4 },
  member_type: { value: "address" },
  is_pool: { value: false },
  utilization: { value: 0 },
  description: { value: null },
  children: { count: 0 },
  ip_addresses: { count: 30 },
};

const POOL_CHILD = {
  __typename: "IpamIPPrefix",
  id: "1808d318-bc0d-b958-d0e1-c511b808cac8",
  prefix: { value: "10.1.0.0/16", prefixlen: 16, version: 4 },
  member_type: { value: "prefix" },
  is_pool: { value: true },
  utilization: { value: 0 },
  description: { value: "Interconnections" },
  children: { count: 16 },
  ip_addresses: { count: 0 },
};

const FREE_BLOCK = {
  __typename: "InternalIPPrefixAvailable",
  id: "18dafbec-c879-c787-11e7-10651a87fdec",
  prefix: { value: "10.3.0.0/16", prefixlen: 16, version: 4 },
  member_type: { value: "address" },
  is_pool: { value: false },
  utilization: { value: null },
  description: { value: null },
  children: { count: 0 },
  ip_addresses: { count: 0 },
};

const response = (nodes: object[], count: number, parent: object | null = PARENT) => ({
  data: {
    parent: { edges: parent ? [{ node: parent }] : [] },
    BuiltinIPPrefix: { count, edges: nodes.map((node) => ({ node })) },
  },
});

const mockedApi = getIpPrefixTreeMapFromApi;

afterEach(() => {
  vi.resetAllMocks();
});

describe("getIpPrefixTreeMap", () => {
  it("maps the parent and real nodes to children with exact blocks and member counts", async () => {
    // GIVEN a page with an address-type child and a pool child
    mockedApi.mockResolvedValue(response([ADDRESS_CHILD, POOL_CHILD], 2));

    // WHEN the map is loaded
    const result = await getIpPrefixTreeMap(PARAMS);

    // THEN the parent and both children carry blocks built from prefixlen and version
    expect(result.parent).toMatchObject({
      id: "parent-id",
      kind: "IpamIPPrefix",
      cidr: "10.0.0.0/8",
      memberType: "prefix",
      utilization: 1,
      size: { family: "ipv4", prefixLength: 8, addressCount: 2n ** 24n },
    });
    expect(
      result.children.map((child) => [
        child.cidr,
        child.memberType,
        child.isPool,
        child.memberCount,
      ])
    ).toEqual([
      ["10.0.0.0/16", "address", false, 30],
      ["10.1.0.0/16", "prefix", true, 16],
    ]);
    expect(result.children[1]?.description).toBe("Interconnections");
    expect(result.children[1]?.size.networkAddress).toBe(10n * 2n ** 24n + 2n ** 16n);
  });

  it("maps available nodes to free blocks", async () => {
    // GIVEN a page with one free block
    mockedApi.mockResolvedValue(response([FREE_BLOCK], 0));

    // WHEN the map is loaded
    const result = await getIpPrefixTreeMap(PARAMS);

    // THEN the block is parsed from its prefix fields
    expect(result.freeBlocks).toEqual([
      {
        cidr: "10.3.0.0/16",
        size: {
          family: "ipv4",
          prefixLength: 16,
          networkAddress: 10n * 2n ** 24n + 3n * 2n ** 16n,
          addressCount: 65536n,
        },
      },
    ]);
  });

  it("is not capped when the count matches the children returned", async () => {
    // GIVEN two children and a count of two
    mockedApi.mockResolvedValue(response([ADDRESS_CHILD, POOL_CHILD], 2));

    // WHEN the map is loaded
    const result = await getIpPrefixTreeMap(PARAMS);

    // THEN it is not capped
    expect(result.totalChildCount).toBe(2);
    expect(result.isCapped).toBe(false);
  });

  it("is capped when the count exceeds the children returned", async () => {
    // GIVEN one child and a count of 1,200
    mockedApi.mockResolvedValue(response([POOL_CHILD], 1200));

    // WHEN the map is loaded
    const result = await getIpPrefixTreeMap(PARAMS);

    // THEN it is capped
    expect(result.isCapped).toBe(true);
    expect(result.totalChildCount).toBe(1200);
  });

  it("drops a node whose prefix fields are incomplete without counting it beyond the cap", async () => {
    // GIVEN a child without a prefix length
    const broken = {
      ...ADDRESS_CHILD,
      prefix: { value: "10.0.0.0/16", prefixlen: null, version: 4 },
    };
    mockedApi.mockResolvedValue(response([broken, POOL_CHILD], 2));

    // WHEN the map is loaded
    const result = await getIpPrefixTreeMap(PARAMS);

    // THEN only the valid child remains and the map is not capped
    expect(result.children.map((child) => child.cidr)).toEqual(["10.1.0.0/16"]);
    expect(result.totalChildCount).toBe(1);
    expect(result.isCapped).toBe(false);
  });

  it("passes the parent id, limit, branch and date through to the api", async () => {
    // GIVEN any page
    mockedApi.mockResolvedValue(response([], 0));

    // WHEN the map is loaded
    await getIpPrefixTreeMap(PARAMS);

    // THEN the api receives the same params
    expect(mockedApi).toHaveBeenCalledWith(PARAMS);
  });

  it("rejects when the parent prefix is missing from the response", async () => {
    // GIVEN a response without the parent
    mockedApi.mockResolvedValue(response([], 0, null));

    // WHEN the map is loaded
    // THEN it rejects
    await expect(getIpPrefixTreeMap(PARAMS)).rejects.toThrow(/parent prefix/);
  });

  it("rejects with the messages of the errors the api returned", async () => {
    // GIVEN an error response
    mockedApi.mockResolvedValue({ data: undefined, errors: [{ message: "boom" }] });

    // WHEN the map is loaded
    // THEN it rejects with the message
    await expect(getIpPrefixTreeMap(PARAMS)).rejects.toThrow("boom");
  });
});
