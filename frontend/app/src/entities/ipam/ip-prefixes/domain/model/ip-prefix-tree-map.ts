export const TREE_MAP_CHILD_LIMIT = 1000;

// Blocks narrower than this many bits below the parent are grouped into the cell that contains them.
export const TREE_MAP_CELL_DEPTH = 12;

export const TREE_MAP_ASPECT_RATIO = 2;

export type IpFamily = "ipv4" | "ipv6";

export type MemberType = "prefix" | "address";

/** The position and extent of one CIDR block, exact for both address families. */
export interface PrefixSize {
  family: IpFamily;
  prefixLength: number;
  networkAddress: bigint;
  addressCount: bigint;
}

export interface TreeMapChild {
  id: string;
  kind: string;
  cidr: string;
  size: PrefixSize;
  memberType: MemberType;
  isPool: boolean;
  utilization: number | null;
  description: string | null;
  memberCount: number;
}

export interface TreeMapFreeBlock {
  cidr: string;
  size: PrefixSize;
}

export interface TreeMapParent {
  id: string;
  kind: string;
  cidr: string;
  size: PrefixSize;
  memberType: MemberType;
  utilization: number | null;
}

export interface TreeMapData {
  parent: TreeMapParent;
  children: TreeMapChild[];
  freeBlocks: TreeMapFreeBlock[];
  totalChildCount: number;
  isCapped: boolean;
}

interface TreeMapTileBase {
  key: string;
  label: string;
  /** The block the tile occupies; the layout places it from this. */
  size: PrefixSize;
}

interface TreeMapAllocatedTile extends TreeMapTileBase {
  kind: "allocated";
  child: TreeMapChild;
}

interface TreeMapFreeTile extends TreeMapTileBase {
  kind: "free";
  block: TreeMapFreeBlock;
}

/** A cell holding at least one child prefix too small to draw on its own. */
interface TreeMapAggregateAllocatedTile extends TreeMapTileBase {
  kind: "aggregate-allocated";
  children: TreeMapChild[];
  freeBlocks: TreeMapFreeBlock[];
}

/** A cell holding only free blocks too small to draw on their own. */
interface TreeMapAggregateFreeTile extends TreeMapTileBase {
  kind: "aggregate-free";
  freeBlocks: TreeMapFreeBlock[];
}

/** Address space after the last fetched block when the child limit cut the page short. */
interface TreeMapNotLoadedTile extends TreeMapTileBase {
  kind: "not-loaded";
  hiddenChildCount: number;
}

export type TreeMapTile =
  | TreeMapAllocatedTile
  | TreeMapFreeTile
  | TreeMapAggregateAllocatedTile
  | TreeMapAggregateFreeTile
  | TreeMapNotLoadedTile;

export interface TreeMapRect {
  tile: TreeMapTile;
  x: number;
  y: number;
  width: number;
  height: number;
}
