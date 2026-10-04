import { describe, expect, it } from "vitest";

import type {
  PrefixSize,
  TreeMapTile,
} from "@/entities/ipam/ip-prefixes/domain/model/ip-prefix-tree-map";
import { buildTreeMapTiles } from "@/entities/ipam/ip-prefixes/domain/rules/build-tree-map-tiles";
import { blockEnd, formatCidr } from "@/entities/ipam/ip-prefixes/domain/rules/prefix-size";

import {
  generateSlash18ChildrenOfDemoSupernet,
  generateTreeMapChild,
  generateTreeMapFreeBlock,
  generateTreeMapParent,
} from "../../../../../../tests/fake/ip-prefix-tree-map";

const DEMO_PARENT = generateTreeMapParent({ cidr: "10.0.0.0/8" });
const DEMO_CHILDREN = ["10.0.0.0/16", "10.1.0.0/16", "10.2.0.0/16"].map((cidr) =>
  generateTreeMapChild({ cidr })
);
const DEMO_FREE_BLOCKS = [
  "10.3.0.0/16",
  "10.4.0.0/14",
  "10.8.0.0/13",
  "10.16.0.0/12",
  "10.32.0.0/11",
  "10.64.0.0/10",
  "10.128.0.0/9",
].map((cidr) => generateTreeMapFreeBlock({ cidr }));

const sumAddressCounts = (tiles: TreeMapTile[]): bigint =>
  tiles.reduce((sum, tile) => sum + tile.size.addressCount, 0n);

const overlaps = (left: PrefixSize, right: PrefixSize): boolean =>
  left.networkAddress < blockEnd(right) && right.networkAddress < blockEnd(left);

const expectDisjoint = (tiles: TreeMapTile[]) => {
  for (const [index, tile] of tiles.entries()) {
    for (const other of tiles.slice(index + 1)) {
      expect(overlaps(tile.size, other.size), `${tile.key} overlaps ${other.key}`).toBe(false);
    }
  }
};

describe("buildTreeMapTiles", () => {
  it("produces one tile per child and free block of the demo /8, in address order", () => {
    // GIVEN the demo supernet's three /16 children and its free blocks
    // WHEN the tiles are built
    const tiles = buildTreeMapTiles({
      parent: DEMO_PARENT,
      children: DEMO_CHILDREN,
      freeBlocks: DEMO_FREE_BLOCKS,
      totalChildCount: 3,
    });

    // THEN the tiles follow the address order of the blocks they cover
    expect(tiles.map((tile) => tile.key)).toEqual([
      "10.0.0.0/16",
      "10.1.0.0/16",
      "10.2.0.0/16",
      "10.3.0.0/16",
      "10.4.0.0/14",
      "10.8.0.0/13",
      "10.16.0.0/12",
      "10.32.0.0/11",
      "10.64.0.0/10",
      "10.128.0.0/9",
    ]);
  });

  it("covers the parent exactly once", () => {
    // GIVEN the demo supernet
    // WHEN the tiles are built
    const tiles = buildTreeMapTiles({
      parent: DEMO_PARENT,
      children: DEMO_CHILDREN,
      freeBlocks: DEMO_FREE_BLOCKS,
      totalChildCount: 3,
    });

    // THEN the tiles sum to the parent and never overlap
    expect(sumAddressCounts(tiles)).toBe(2n ** 24n);
    expectDisjoint(tiles);
  });

  it("keeps a child with unknown utilization as an allocated tile", () => {
    // GIVEN a child whose utilization could not be computed
    const child = generateTreeMapChild({ cidr: "10.0.0.0/9", utilization: null });

    // WHEN the tiles are built
    const tiles = buildTreeMapTiles({
      parent: DEMO_PARENT,
      children: [child],
      freeBlocks: [generateTreeMapFreeBlock({ cidr: "10.128.0.0/9" })],
      totalChildCount: 1,
    });

    // THEN the allocated tile keeps the null
    expect(tiles[0]?.kind).toBe("allocated");
    expect(tiles[0]?.kind === "allocated" && tiles[0].child.utilization).toBeNull();
  });

  it("groups a /32 child of a /8 into the /20 cell that contains it", () => {
    // GIVEN three /16 children and one /32 inside 10.5.4.0/20
    const children = [...DEMO_CHILDREN, generateTreeMapChild({ cidr: "10.5.4.7/32" })];

    // WHEN the tiles are built
    const tiles = buildTreeMapTiles({
      parent: DEMO_PARENT,
      children,
      freeBlocks: [],
      totalChildCount: 4,
    });

    // THEN the /32 is not its own tile and the cell tile sits at the /20 in address space
    const cell = tiles.find((tile) => tile.kind === "aggregate-allocated");
    expect(tiles.some((tile) => tile.key === "10.5.4.7/32")).toBe(false);
    expect(cell && formatCidr(cell.size)).toBe("10.5.0.0/20");
    expect(cell?.kind === "aggregate-allocated" && cell.children.map((c) => c.cidr)).toEqual([
      "10.5.4.7/32",
    ]);
    expect(cell?.label).toBe("10.5.0.0/20: 1 smaller prefix");
  });

  it("groups small free blocks into a free cell and small children with free blocks into one cell", () => {
    // GIVEN a /24 child and the /24 free blocks around it inside the same /20, plus free /24s in another /20
    const children = [generateTreeMapChild({ cidr: "10.9.0.0/24" })];
    const freeBlocks = [
      generateTreeMapFreeBlock({ cidr: "10.9.1.0/24" }),
      generateTreeMapFreeBlock({ cidr: "10.9.2.0/23" }),
      generateTreeMapFreeBlock({ cidr: "10.9.16.0/24" }),
    ];

    // WHEN the tiles are built
    const tiles = buildTreeMapTiles({
      parent: DEMO_PARENT,
      children,
      freeBlocks,
      totalChildCount: 1,
    });

    // THEN the first /20 is an allocated cell holding both kinds and the second is a free cell
    expect(tiles.map((tile) => [tile.kind, formatCidr(tile.size)])).toEqual([
      ["aggregate-allocated", "10.9.0.0/20"],
      ["aggregate-free", "10.9.16.0/20"],
    ]);
    const mixed = tiles[0];
    expect(mixed?.kind === "aggregate-allocated" && mixed.freeBlocks.length).toBe(2);
  });

  it("keeps a child exactly at the cell depth as its own tile", () => {
    // GIVEN a /20 child of a /8, which is exactly 1/4096 of the parent
    const children = [generateTreeMapChild({ cidr: "10.7.16.0/20" })];

    // WHEN the tiles are built
    const tiles = buildTreeMapTiles({
      parent: DEMO_PARENT,
      children,
      freeBlocks: [],
      totalChildCount: 1,
    });

    // THEN it is allocated, not grouped
    expect(tiles.map((tile) => tile.kind)).toEqual(["allocated"]);
  });

  it("marks the space after the last fetched block as not loaded when the page is capped", () => {
    // GIVEN 1,000 /18 children fetched out of 1,200, with the free blocks the backend returns
    const children = generateSlash18ChildrenOfDemoSupernet(1000);
    const lastEnd = blockEnd(children[999]?.size ?? DEMO_PARENT.size);

    // WHEN the tiles are built
    const tiles = buildTreeMapTiles({
      parent: DEMO_PARENT,
      children,
      freeBlocks: [],
      totalChildCount: 1200,
    });

    // THEN not-loaded tiles start where the fetched blocks end, cover up to the parent's end exactly,
    // and none of them is drawn as free
    const notLoaded = tiles.filter((tile) => tile.kind === "not-loaded");
    expect(notLoaded.length).toBeGreaterThan(0);
    expect(notLoaded[0]?.size.networkAddress).toBe(lastEnd);
    expect(sumAddressCounts(notLoaded)).toBe(blockEnd(DEMO_PARENT.size) - lastEnd);
    expect(tiles.some((tile) => tile.kind === "free")).toBe(false);
    expect(
      notLoaded.every((tile) => tile.kind === "not-loaded" && tile.hiddenChildCount === 200)
    ).toBe(true);
    expect(sumAddressCounts(tiles)).toBe(2n ** 24n);
    expectDisjoint(tiles);
  });

  it("produces no not-loaded tile when every child was fetched", () => {
    // GIVEN the demo supernet with its count matching its children
    // WHEN the tiles are built
    const tiles = buildTreeMapTiles({
      parent: DEMO_PARENT,
      children: DEMO_CHILDREN,
      freeBlocks: DEMO_FREE_BLOCKS,
      totalChildCount: 3,
    });

    // THEN nothing is marked as not loaded
    expect(tiles.some((tile) => tile.kind === "not-loaded")).toBe(false);
  });

  it("handles IPv6 extremes exactly", () => {
    // GIVEN a /32 with a /44 (at the cell depth), a /48 and a /128 child
    const parent = generateTreeMapParent({ cidr: "2001:db8::/32" });
    const children = [
      generateTreeMapChild({ cidr: "2001:db8::/44" }),
      generateTreeMapChild({ cidr: "2001:db8:1000::/48" }),
      generateTreeMapChild({ cidr: "2001:db8:2000::1/128" }),
    ];
    const freeBlocks = [generateTreeMapFreeBlock({ cidr: "2001:db8:8000::/33" })];

    // WHEN the tiles are built
    const tiles = buildTreeMapTiles({ parent, children, freeBlocks, totalChildCount: 3 });

    // THEN the /44 stays allocated, the smaller two land in their own /44 cells, and sums stay exact
    expect(tiles.map((tile) => [tile.kind, formatCidr(tile.size)])).toEqual([
      ["allocated", "2001:db8::/44"],
      ["aggregate-allocated", "2001:db8:1000::/44"],
      ["aggregate-allocated", "2001:db8:2000::/44"],
      ["free", "2001:db8:8000::/33"],
    ]);
    expectDisjoint(tiles);
    expect(sumAddressCounts(tiles)).toBeLessThanOrEqual(2n ** 96n);
  });
});
