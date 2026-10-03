export const TREE_MAP_CHILD_LIMIT = 1000;

// A BigInt divisor keeps the aggregation threshold exact for IPv6 address counts beyond 2^53.
export const TREE_MAP_MIN_TILE_DIVISOR = 4096n;

export const TREE_MAP_ASPECT_RATIO = 2;

type IpFamily = "ipv4" | "ipv6";

type MemberType = "prefix" | "address";

export interface PrefixSize {
  family: IpFamily;
  prefixLength: number;
  addressCount: bigint;
}

export interface TreeMapChild {
  id: string;
  kind: string;
  cidr: string;
  size: PrefixSize;
  memberType: MemberType;
  utilization: number | null;
  description: string | null;
  memberCount: number;
}

export interface TreeMapFreeBlock {
  cidr: string;
  size: PrefixSize;
}

export interface TreeMapData {
  parent: {
    id: string;
    cidr: string;
    size: PrefixSize;
    memberType: MemberType;
    utilization: number | null;
  };
  children: TreeMapChild[];
  freeBlocks: TreeMapFreeBlock[];
  totalChildCount: number;
  isCapped: boolean;
}

interface TreeMapTileBase {
  key: string;
  addressCount: bigint;
  weight: number;
  label: string;
}

interface TreeMapAllocatedTile extends TreeMapTileBase {
  kind: "allocated";
  child: TreeMapChild;
}

interface TreeMapFreeTile extends TreeMapTileBase {
  kind: "free";
  block: TreeMapFreeBlock;
}

interface TreeMapAggregateAllocatedTile extends TreeMapTileBase {
  kind: "aggregate-allocated";
  members: TreeMapChild[];
}

interface TreeMapAggregateFreeTile extends TreeMapTileBase {
  kind: "aggregate-free";
  members: TreeMapFreeBlock[];
}

interface TreeMapRemainderTile extends TreeMapTileBase {
  kind: "remainder";
  hiddenChildCount: number;
}

export type TreeMapTile =
  | TreeMapAllocatedTile
  | TreeMapFreeTile
  | TreeMapAggregateAllocatedTile
  | TreeMapAggregateFreeTile
  | TreeMapRemainderTile;

export interface TreeMapRect {
  tile: TreeMapTile;
  x: number;
  y: number;
  width: number;
  height: number;
}
