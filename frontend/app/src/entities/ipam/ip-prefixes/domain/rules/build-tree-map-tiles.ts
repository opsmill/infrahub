import {
  type PrefixSize,
  TREE_MAP_MIN_TILE_DIVISOR,
  type TreeMapChild,
  type TreeMapData,
  type TreeMapFreeBlock,
  type TreeMapTile,
} from "@/entities/ipam/ip-prefixes/domain/model/ip-prefix-tree-map";

export type BuildTreeMapTilesParams = Pick<
  TreeMapData,
  "children" | "freeBlocks" | "totalChildCount"
> & { parent: Pick<TreeMapData["parent"], "size"> };

type Sized = { size: PrefixSize };

type Partition<T> = { large: T[]; small: T[] };

function partitionBySize<T extends Sized>(items: T[], threshold: bigint): Partition<T> {
  const partition: Partition<T> = { large: [], small: [] };
  for (const item of items) {
    (item.size.addressCount >= threshold ? partition.large : partition.small).push(item);
  }
  return partition;
}

function sumAddressCounts(items: Sized[]): bigint {
  return items.reduce((sum, item) => sum + item.size.addressCount, 0n);
}

function pluralise(count: number, singular: string, plural: string): string {
  return `${count} ${count === 1 ? singular : plural}`;
}

// Address counts are powers of two, which doubles represent exactly, so the division is exact.
// Single-prefix counts are powers of two, so only aggregate and remainder weights carry rounding.
function weightOf(addressCount: bigint, parentAddressCount: bigint): number {
  return Number(addressCount) / Number(parentAddressCount);
}

function toAllocatedTile(child: TreeMapChild, parentAddressCount: bigint): TreeMapTile {
  return {
    kind: "allocated",
    key: child.cidr,
    label: child.cidr,
    addressCount: child.size.addressCount,
    weight: weightOf(child.size.addressCount, parentAddressCount),
    child,
  };
}

function toFreeTile(block: TreeMapFreeBlock, parentAddressCount: bigint): TreeMapTile {
  return {
    kind: "free",
    key: block.cidr,
    label: block.cidr,
    addressCount: block.size.addressCount,
    weight: weightOf(block.size.addressCount, parentAddressCount),
    block,
  };
}

function toAggregateAllocatedTile(
  members: TreeMapChild[],
  parentAddressCount: bigint
): TreeMapTile[] {
  if (members.length === 0) return [];
  const addressCount = sumAddressCounts(members);
  return [
    {
      kind: "aggregate-allocated",
      key: "aggregate-allocated",
      label: pluralise(members.length, "smaller prefix", "smaller prefixes"),
      addressCount,
      weight: weightOf(addressCount, parentAddressCount),
      members,
    },
  ];
}

function toAggregateFreeTile(
  members: TreeMapFreeBlock[],
  parentAddressCount: bigint
): TreeMapTile[] {
  if (members.length === 0) return [];
  const addressCount = sumAddressCounts(members);
  return [
    {
      kind: "aggregate-free",
      key: "aggregate-free",
      label: pluralise(members.length, "smaller free block", "smaller free blocks"),
      addressCount,
      weight: weightOf(addressCount, parentAddressCount),
      members,
    },
  ];
}

function toRemainderTile(
  { parent, children, freeBlocks, totalChildCount }: BuildTreeMapTilesParams,
  parentAddressCount: bigint
): TreeMapTile[] {
  const hiddenChildCount = totalChildCount - children.length;
  if (hiddenChildCount <= 0) return [];

  const addressCount =
    parentAddressCount - sumAddressCounts(children) - sumAddressCounts(freeBlocks);
  if (addressCount <= 0n) return [];

  return [
    {
      kind: "remainder",
      key: "remainder",
      label: pluralise(hiddenChildCount, "more child", "more children"),
      addressCount,
      weight: weightOf(addressCount, parent.size.addressCount),
      hiddenChildCount,
    },
  ];
}

/**
 * Turns a prefix's children and free blocks into tiles whose address counts sum exactly to the
 * parent's, aggregating anything smaller than 1/4096 of the parent and adding one remainder tile
 * for the space held by children beyond the fetched window.
 */
export function buildTreeMapTiles(params: BuildTreeMapTilesParams): TreeMapTile[] {
  const parentAddressCount = params.parent.size.addressCount;
  const threshold = parentAddressCount / TREE_MAP_MIN_TILE_DIVISOR;

  const children = partitionBySize(params.children, threshold);
  const freeBlocks = partitionBySize(params.freeBlocks, threshold);

  const tiles: TreeMapTile[] = [
    ...children.large.map((child) => toAllocatedTile(child, parentAddressCount)),
    ...freeBlocks.large.map((block) => toFreeTile(block, parentAddressCount)),
    ...toAggregateAllocatedTile(children.small, parentAddressCount),
    ...toAggregateFreeTile(freeBlocks.small, parentAddressCount),
    ...toRemainderTile(params, parentAddressCount),
  ];

  // Array sort is stable, so equal weights keep the received address order.
  return tiles.sort((left, right) => right.weight - left.weight);
}
