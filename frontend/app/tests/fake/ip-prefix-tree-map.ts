import type {
  PrefixSize,
  TreeMapChild,
  TreeMapFreeBlock,
  TreeMapParent,
  TreeMapRect,
  TreeMapTile,
} from "@/entities/ipam/ip-prefixes/domain/model/ip-prefix-tree-map";

import { buildPrefixSize } from "../../src/entities/ipam/ip-prefixes/domain/rules/prefix-size";

/** Builds a block from a CIDR string the way the API fields would describe it. */
export const sizeOf = (cidr: string): PrefixSize =>
  buildPrefixSize({
    cidr,
    prefixLength: Number(cidr.split("/")[1]),
    version: cidr.includes(":") ? 6 : 4,
  });

export const generateTreeMapParent = (overrides: Partial<TreeMapParent> = {}): TreeMapParent => {
  const cidr = overrides.cidr ?? "10.0.0.0/8";

  return {
    id: "parent-id",
    kind: "IpamIPPrefix",
    cidr,
    size: sizeOf(cidr),
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
    size: sizeOf(cidr),
    memberType: "prefix",
    isPool: false,
    utilization: 0,
    description: null,
    memberCount: 0,
    ...overrides,
  };
};

/** Sequential /18 children of 10.0.0.0/8 in address order; valid for counts up to 1,024. */
export const generateSlash18ChildrenOfDemoSupernet = (count: number): TreeMapChild[] =>
  Array.from({ length: count }, (_, index) => {
    const second = Math.floor(index / 4);
    const third = (index % 4) * 64;
    return generateTreeMapChild({ cidr: `10.${second}.${third}.0/18` });
  });

export const generateTreeMapFreeBlock = (
  overrides: Partial<TreeMapFreeBlock> = {}
): TreeMapFreeBlock => {
  const cidr = overrides.cidr ?? "10.3.0.0/16";

  return {
    cidr,
    size: sizeOf(cidr),
    ...overrides,
  };
};

export const generateAllocatedTile = (
  overrides: { child?: Partial<TreeMapChild> } = {}
): TreeMapTile => {
  const child = generateTreeMapChild(overrides.child);

  return { kind: "allocated", key: child.cidr, label: child.cidr, size: child.size, child };
};

export const generateFreeTile = (
  overrides: { block?: Partial<TreeMapFreeBlock> } = {}
): TreeMapTile => {
  const block = generateTreeMapFreeBlock(overrides.block);

  return { kind: "free", key: block.cidr, label: block.cidr, size: block.size, block };
};

export const generateAggregateAllocatedTile = (
  overrides: { cidr?: string; children?: TreeMapChild[]; freeBlocks?: TreeMapFreeBlock[] } = {}
): TreeMapTile => {
  const cidr = overrides.cidr ?? "10.0.0.0/20";
  const children = overrides.children ?? [generateTreeMapChild({ cidr: "10.0.0.0/24" })];

  return {
    kind: "aggregate-allocated",
    key: `cell:${cidr}`,
    label: `${cidr}: ${children.length} smaller prefix${children.length === 1 ? "" : "es"}`,
    size: sizeOf(cidr),
    children,
    freeBlocks: overrides.freeBlocks ?? [],
  };
};

export const generateAggregateFreeTile = (
  overrides: { cidr?: string; freeBlocks?: TreeMapFreeBlock[] } = {}
): TreeMapTile => {
  const cidr = overrides.cidr ?? "10.0.16.0/20";
  const freeBlocks = overrides.freeBlocks ?? [generateTreeMapFreeBlock({ cidr: "10.0.16.0/24" })];

  return {
    kind: "aggregate-free",
    key: `cell:${cidr}`,
    label: `${cidr}: ${freeBlocks.length} smaller free block${freeBlocks.length === 1 ? "" : "s"}`,
    size: sizeOf(cidr),
    freeBlocks,
  };
};

export const generateNotLoadedTile = (
  overrides: { cidr?: string; hiddenChildCount?: number } = {}
): TreeMapTile => {
  const cidr = overrides.cidr ?? "10.128.0.0/9";
  const hiddenChildCount = overrides.hiddenChildCount ?? 200;

  return {
    kind: "not-loaded",
    key: `not-loaded:${cidr}`,
    label: "Not loaded",
    size: sizeOf(cidr),
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
