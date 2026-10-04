import {
  type PrefixSize,
  TREE_MAP_CELL_DEPTH,
  type TreeMapChild,
  type TreeMapData,
  type TreeMapFreeBlock,
  type TreeMapTile,
} from "@/entities/ipam/ip-prefixes/domain/model/ip-prefix-tree-map";
import {
  blockEnd,
  containingBlock,
  formatCidr,
  rangeToBlocks,
} from "@/entities/ipam/ip-prefixes/domain/rules/prefix-size";

export type BuildTreeMapTilesParams = Pick<
  TreeMapData,
  "children" | "freeBlocks" | "totalChildCount"
> & { parent: Pick<TreeMapData["parent"], "size"> };

interface Cell {
  size: PrefixSize;
  children: TreeMapChild[];
  freeBlocks: TreeMapFreeBlock[];
}

function pluralise(count: number, singular: string, plural: string): string {
  return `${count} ${count === 1 ? singular : plural}`;
}

function byAddress(left: { size: PrefixSize }, right: { size: PrefixSize }): number {
  if (left.size.networkAddress === right.size.networkAddress) return 0;
  return left.size.networkAddress < right.size.networkAddress ? -1 : 1;
}

function toAllocatedTile(child: TreeMapChild): TreeMapTile {
  return { kind: "allocated", key: child.cidr, label: child.cidr, size: child.size, child };
}

function toFreeTile(block: TreeMapFreeBlock): TreeMapTile {
  return { kind: "free", key: block.cidr, label: block.cidr, size: block.size, block };
}

function toCellTile(cell: Cell): TreeMapTile {
  const cidr = formatCidr(cell.size);
  if (cell.children.length > 0) {
    return {
      kind: "aggregate-allocated",
      key: `cell:${cidr}`,
      label: `${cidr}: ${pluralise(cell.children.length, "smaller prefix", "smaller prefixes")}`,
      size: cell.size,
      children: cell.children,
      freeBlocks: cell.freeBlocks,
    };
  }
  return {
    kind: "aggregate-free",
    key: `cell:${cidr}`,
    label: `${cidr}: ${pluralise(cell.freeBlocks.length, "smaller free block", "smaller free blocks")}`,
    size: cell.size,
    freeBlocks: cell.freeBlocks,
  };
}

/** Groups blocks too small to draw into the fixed-size cell that contains each of them. */
function groupIntoCells(
  parent: PrefixSize,
  children: TreeMapChild[],
  freeBlocks: TreeMapFreeBlock[],
  cellPrefixLength: number
): Cell[] {
  const cells = new Map<bigint, Cell>();
  const cellFor = (address: bigint): Cell => {
    const size = containingBlock(address, cellPrefixLength, parent.family);
    const existing = cells.get(size.networkAddress);
    if (existing) return existing;
    const cell: Cell = { size, children: [], freeBlocks: [] };
    cells.set(size.networkAddress, cell);
    return cell;
  };
  for (const child of children) cellFor(child.size.networkAddress).children.push(child);
  for (const block of freeBlocks) cellFor(block.size.networkAddress).freeBlocks.push(block);
  return [...cells.values()];
}

/**
 * The page is cut at the child limit, and the backend only reports free space up to the last
 * block it returned, so everything after that block is unknown rather than free.
 */
function toNotLoadedTiles(params: BuildTreeMapTilesParams, lastEnd: bigint): TreeMapTile[] {
  const hiddenChildCount = params.totalChildCount - params.children.length;
  const parentEnd = blockEnd(params.parent.size);
  if (hiddenChildCount <= 0 || lastEnd >= parentEnd) return [];

  return rangeToBlocks(lastEnd, parentEnd, params.parent.size.family).map((size) => ({
    kind: "not-loaded",
    key: `not-loaded:${formatCidr(size)}`,
    label: "Not loaded",
    size,
    hiddenChildCount,
  }));
}

/**
 * Turns a prefix's children and free blocks into tiles in address order, each tied to the exact
 * block it covers. Blocks deeper than the cell depth below the parent are grouped per cell, and
 * the space after the last fetched block becomes not-loaded tiles when the child limit applied.
 */
export function buildTreeMapTiles(params: BuildTreeMapTilesParams): TreeMapTile[] {
  const parent = params.parent.size;
  const cellPrefixLength = parent.prefixLength + TREE_MAP_CELL_DEPTH;
  const isSmall = (item: { size: PrefixSize }) => item.size.prefixLength > cellPrefixLength;

  const largeChildren = params.children.filter((child) => !isSmall(child));
  const largeFree = params.freeBlocks.filter((block) => !isSmall(block));
  const cells = groupIntoCells(
    parent,
    params.children.filter(isSmall),
    params.freeBlocks.filter(isSmall),
    cellPrefixLength
  );

  const loaded = [...params.children, ...params.freeBlocks];
  const lastEnd = loaded.reduce(
    (end, item) => (blockEnd(item.size) > end ? blockEnd(item.size) : end),
    parent.networkAddress
  );

  const tiles: TreeMapTile[] = [
    ...largeChildren.map(toAllocatedTile),
    ...largeFree.map(toFreeTile),
    ...cells.map(toCellTile),
    ...toNotLoadedTiles(params, lastEnd),
  ];

  return tiles.sort(byAddress);
}
