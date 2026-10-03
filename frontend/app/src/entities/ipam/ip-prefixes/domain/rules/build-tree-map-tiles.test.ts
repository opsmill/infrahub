import { describe, expect, it } from "vitest";

import { buildTreeMapTiles } from "@/entities/ipam/ip-prefixes/domain/rules/build-tree-map-tiles";

import {
  generateTreeMapChild,
  generateTreeMapFreeBlock,
  generateTreeMapParent,
} from "../../../../../../tests/fake/ip-prefix-tree-map";

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

describe("buildTreeMapTiles", () => {
  it("produces one tile per child and free block of the demo /8", () => {
    // GIVEN
    const parent = generateTreeMapParent({ cidr: "10.0.0.0/8" });

    // WHEN
    const tiles = buildTreeMapTiles({
      parent,
      children: DEMO_CHILDREN,
      freeBlocks: DEMO_FREE_BLOCKS,
      totalChildCount: DEMO_CHILDREN.length,
    });

    // THEN
    expect(tiles.map((tile) => [tile.kind, tile.label])).toEqual([
      ["free", "10.128.0.0/9"],
      ["free", "10.64.0.0/10"],
      ["free", "10.32.0.0/11"],
      ["free", "10.16.0.0/12"],
      ["free", "10.8.0.0/13"],
      ["free", "10.4.0.0/14"],
      ["allocated", "10.0.0.0/16"],
      ["allocated", "10.1.0.0/16"],
      ["allocated", "10.2.0.0/16"],
      ["free", "10.3.0.0/16"],
    ]);
  });

  it("sums the tile address counts exactly to the parent's address count", () => {
    // GIVEN
    const parent = generateTreeMapParent({ cidr: "10.0.0.0/8" });

    // WHEN
    const tiles = buildTreeMapTiles({
      parent,
      children: DEMO_CHILDREN,
      freeBlocks: DEMO_FREE_BLOCKS,
      totalChildCount: DEMO_CHILDREN.length,
    });

    // THEN
    expect(tiles.reduce((sum, tile) => sum + tile.addressCount, 0n)).toBe(2n ** 24n);
  });

  it("sums the tile weights to one", () => {
    // GIVEN
    const parent = generateTreeMapParent({ cidr: "10.0.0.0/8" });

    // WHEN
    const tiles = buildTreeMapTiles({
      parent,
      children: DEMO_CHILDREN,
      freeBlocks: DEMO_FREE_BLOCKS,
      totalChildCount: DEMO_CHILDREN.length,
    });

    // THEN
    expect(Math.abs(tiles.reduce((sum, tile) => sum + tile.weight, 0) - 1)).toBeLessThan(1e-6);
  });

  it("produces no free tile for a fully allocated parent", () => {
    // GIVEN
    const parent = generateTreeMapParent({ cidr: "10.0.0.0/8" });
    const children = ["10.0.0.0/9", "10.128.0.0/9"].map((cidr) => generateTreeMapChild({ cidr }));

    // WHEN
    const tiles = buildTreeMapTiles({ parent, children, freeBlocks: [], totalChildCount: 2 });

    // THEN
    expect(tiles.map((tile) => tile.kind)).toEqual(["allocated", "allocated"]);
  });

  it("produces two free tiles for an empty parent split into two halves", () => {
    // GIVEN
    const parent = generateTreeMapParent({ cidr: "10.0.0.0/8" });
    const freeBlocks = ["10.0.0.0/9", "10.128.0.0/9"].map((cidr) =>
      generateTreeMapFreeBlock({ cidr })
    );

    // WHEN
    const tiles = buildTreeMapTiles({ parent, children: [], freeBlocks, totalChildCount: 0 });

    // THEN
    expect(tiles.map((tile) => [tile.kind, tile.weight])).toEqual([
      ["free", 0.5],
      ["free", 0.5],
    ]);
  });

  it("keeps a null utilization on the allocated tile", () => {
    // GIVEN
    const parent = generateTreeMapParent({ cidr: "10.0.0.0/8" });
    const children = [generateTreeMapChild({ cidr: "10.0.0.0/9", utilization: null })];

    // WHEN
    const tiles = buildTreeMapTiles({ parent, children, freeBlocks: [], totalChildCount: 1 });

    // THEN
    expect(tiles).toEqual([
      expect.objectContaining({
        kind: "allocated",
        child: expect.objectContaining({ utilization: null }),
      }),
    ]);
  });

  it("sorts tiles by weight descending and keeps ties in the received address order", () => {
    // GIVEN
    const parent = generateTreeMapParent({ cidr: "10.0.0.0/8" });
    const children = ["10.1.0.0/16", "10.0.0.0/16", "10.2.0.0/15", "10.128.0.0/9"].map((cidr) =>
      generateTreeMapChild({ cidr })
    );
    const freeBlocks = ["10.4.0.0/14", "10.64.0.0/10", "10.8.0.0/13", "10.32.0.0/11"].map((cidr) =>
      generateTreeMapFreeBlock({ cidr })
    );

    // WHEN
    const tiles = buildTreeMapTiles({ parent, children, freeBlocks, totalChildCount: 4 });

    // THEN
    expect(tiles.map((tile) => tile.label)).toEqual([
      "10.128.0.0/9",
      "10.64.0.0/10",
      "10.32.0.0/11",
      "10.8.0.0/13",
      "10.4.0.0/14",
      "10.2.0.0/15",
      "10.1.0.0/16",
      "10.0.0.0/16",
    ]);
  });

  it("uses the parent's exact address count for IPv6 weights", () => {
    // GIVEN
    const parent = generateTreeMapParent({ cidr: "2001:db8::/32" });
    const children = [generateTreeMapChild({ cidr: "2001:db8::/33" })];
    const freeBlocks = [generateTreeMapFreeBlock({ cidr: "2001:db8:8000::/33" })];

    // WHEN
    const tiles = buildTreeMapTiles({ parent, children, freeBlocks, totalChildCount: 1 });

    // THEN
    expect(tiles.map((tile) => [tile.addressCount, tile.weight])).toEqual([
      [2n ** 95n, 0.5],
      [2n ** 95n, 0.5],
    ]);
  });
});
