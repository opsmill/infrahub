import type {
  TreeMapChild,
  TreeMapData,
  TreeMapFreeBlock,
  TreeMapRect,
  TreeMapTile,
} from "@/entities/ipam/ip-prefixes/domain/model/ip-prefix-tree-map";

import { parsePrefixLength } from "../../src/entities/ipam/ip-prefixes/domain/rules/parse-prefix-length";

export const generateTreeMapParent = (
  overrides: Partial<TreeMapData["parent"]> = {}
): TreeMapData["parent"] => {
  const cidr = overrides.cidr ?? "10.0.0.0/8";

  return {
    id: "parent-id",
    cidr,
    size: parsePrefixLength(cidr),
    memberType: "prefix",
    utilization: 0,
    ...overrides,
  };
};

export const generateTreeMapChild = (overrides: Partial<TreeMapChild> = {}): TreeMapChild => {
  const cidr = overrides.cidr ?? "10.0.0.0/16";

  return {
    id: `child-${cidr}`,
    kind: "IpamIPPrefix",
    cidr,
    size: parsePrefixLength(cidr),
    memberType: "prefix",
    isPool: false,
    utilization: 0,
    description: null,
    memberCount: 0,
    ...overrides,
  };
};

const SLASH_18_ADDRESS_COUNT = 2n ** 14n;
const IPV4_OCTET_RADIX = 256n;

/** Sequential /18 children of 10.0.0.0/8 in address order; valid for counts up to 1,024. */
export const generateSlash18ChildrenOfDemoSupernet = (count: number): TreeMapChild[] =>
  Array.from({ length: count }, (_, index) => {
    const start = 0x0a000000n + BigInt(index) * SLASH_18_ADDRESS_COUNT;
    const octets = [3n, 2n, 1n, 0n].map((position) =>
      ((start / IPV4_OCTET_RADIX ** position) % IPV4_OCTET_RADIX).toString()
    );
    return generateTreeMapChild({ cidr: `${octets.join(".")}/18` });
  });

export const generateTreeMapFreeBlock = (
  overrides: Partial<TreeMapFreeBlock> = {}
): TreeMapFreeBlock => {
  const cidr = overrides.cidr ?? "10.3.0.0/16";

  return {
    cidr,
    size: parsePrefixLength(cidr),
    ...overrides,
  };
};

type TileOverrides = { weight?: number; addressCount?: bigint };

export const generateAllocatedTile = (
  overrides: TileOverrides & { child?: Partial<TreeMapChild> } = {}
): TreeMapTile => {
  const child = generateTreeMapChild(overrides.child);

  return {
    kind: "allocated",
    key: child.cidr,
    label: child.cidr,
    addressCount: overrides.addressCount ?? child.size.addressCount,
    weight: overrides.weight ?? 0.25,
    child,
  };
};

export const generateFreeTile = (
  overrides: TileOverrides & { block?: Partial<TreeMapFreeBlock> } = {}
): TreeMapTile => {
  const block = generateTreeMapFreeBlock(overrides.block);

  return {
    kind: "free",
    key: block.cidr,
    label: block.cidr,
    addressCount: overrides.addressCount ?? block.size.addressCount,
    weight: overrides.weight ?? 0.25,
    block,
  };
};

export const generateAggregateAllocatedTile = (
  overrides: TileOverrides & { members?: TreeMapChild[] } = {}
): TreeMapTile => {
  const members = overrides.members ?? [generateTreeMapChild({ cidr: "10.0.0.0/24" })];

  return {
    kind: "aggregate-allocated",
    key: "aggregate-allocated",
    label: `${members.length} smaller prefix${members.length === 1 ? "" : "es"}`,
    addressCount: overrides.addressCount ?? 256n,
    weight: overrides.weight ?? 0.001,
    members,
  };
};

export const generateAggregateFreeTile = (
  overrides: TileOverrides & { members?: TreeMapFreeBlock[] } = {}
): TreeMapTile => {
  const members = overrides.members ?? [generateTreeMapFreeBlock({ cidr: "10.0.1.0/24" })];

  return {
    kind: "aggregate-free",
    key: "aggregate-free",
    label: `${members.length} smaller free block${members.length === 1 ? "" : "s"}`,
    addressCount: overrides.addressCount ?? 256n,
    weight: overrides.weight ?? 0.001,
    members,
  };
};

export const generateRemainderTile = (
  overrides: TileOverrides & { hiddenChildCount?: number } = {}
): TreeMapTile => {
  const hiddenChildCount = overrides.hiddenChildCount ?? 200;

  return {
    kind: "remainder",
    key: "remainder",
    label: `${hiddenChildCount} more children`,
    addressCount: overrides.addressCount ?? 65536n,
    weight: overrides.weight ?? 0.1,
    hiddenChildCount,
  };
};

export const generateTreeMapRect = (overrides: Partial<TreeMapRect> = {}): TreeMapRect => ({
  tile: generateAllocatedTile(),
  x: 0,
  y: 0,
  width: 50,
  height: 50,
  ...overrides,
});
