import { describe, expect, it } from "vitest";

import type {
  PrefixSize,
  TreeMapTile,
} from "@/entities/ipam/ip-prefixes/domain/model/ip-prefix-tree-map";
import { buildTreeMapTiles } from "@/entities/ipam/ip-prefixes/domain/rules/build-tree-map-tiles";

import {
  generateSlash18ChildrenOfDemoSupernet,
  generateTreeMapChild,
  generateTreeMapFreeBlock,
  generateTreeMapParent,
} from "../../../../../../tests/fake/ip-prefix-tree-map";

type AddressRange = { start: bigint; end: bigint };

const IPV4_OCTET_RADIX = 256n;
const IPV6_GROUP_RADIX = 65536n;

function parseIpv4Start(address: string): bigint {
  return address
    .split(".")
    .reduce((value, octet) => value * IPV4_OCTET_RADIX + BigInt(Number.parseInt(octet, 10)), 0n);
}

function parseIpv6Start(address: string): bigint {
  const [head = "", tail = ""] = address.split("::");
  const headGroups = head === "" ? [] : head.split(":");
  const tailGroups = tail === "" ? [] : tail.split(":");
  const padding = new Array<string>(8 - headGroups.length - tailGroups.length).fill("0");
  return [...headGroups, ...padding, ...tailGroups].reduce(
    (value, group) => value * IPV6_GROUP_RADIX + BigInt(Number.parseInt(group, 16)),
    0n
  );
}

function toAddressRange(cidr: string, size: PrefixSize): AddressRange {
  const address = cidr.slice(0, cidr.lastIndexOf("/"));
  const start = size.family === "ipv6" ? parseIpv6Start(address) : parseIpv4Start(address);
  return { start, end: start + size.addressCount };
}

function collectAddressRanges(tile: TreeMapTile): AddressRange[] {
  switch (tile.kind) {
    case "allocated":
      return [toAddressRange(tile.child.cidr, tile.child.size)];
    case "free":
      return [toAddressRange(tile.block.cidr, tile.block.size)];
    case "aggregate-allocated":
    case "aggregate-free":
      return tile.members.map((member) => toAddressRange(member.cidr, member.size));
    case "remainder":
      return [];
  }
}

function countOverlappingRanges(tiles: TreeMapTile[]): number {
  const ranges = tiles.flatMap(collectAddressRanges);
  return ranges.reduce(
    (overlaps, left, index) =>
      overlaps +
      ranges.slice(index + 1).filter((right) => left.start < right.end && right.start < left.end)
        .length,
    0
  );
}

function sumAddressCounts(tiles: TreeMapTile[]): bigint {
  return tiles.reduce((sum, tile) => sum + tile.addressCount, 0n);
}

function formatIpv6(address: bigint): string {
  return Array.from({ length: 8 }, (_, index) =>
    ((address / IPV6_GROUP_RADIX ** BigInt(7 - index)) % IPV6_GROUP_RADIX).toString(16)
  ).join(":");
}

// One free block per power of two covers everything in 2001:db8::/32 except its first address.
function generateFreeBlocksAroundFirstIpv6Address() {
  return Array.from({ length: 96 }, (_, exponent) => {
    const start = 0x20010db8000000000000000000000000n + 2n ** BigInt(exponent);
    return generateTreeMapFreeBlock({ cidr: `${formatIpv6(start)}/${128 - exponent}` });
  });
}

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

  it("aggregates a /32 child of a /8 into a one-member smaller-prefixes tile", () => {
    // GIVEN
    const parent = generateTreeMapParent({ cidr: "10.0.0.0/8" });
    const children = [...DEMO_CHILDREN, generateTreeMapChild({ cidr: "10.3.0.1/32" })];

    // WHEN
    const tiles = buildTreeMapTiles({ parent, children, freeBlocks: [], totalChildCount: 4 });

    // THEN
    expect(tiles.map((tile) => [tile.kind, tile.label])).toEqual([
      ["allocated", "10.0.0.0/16"],
      ["allocated", "10.1.0.0/16"],
      ["allocated", "10.2.0.0/16"],
      ["aggregate-allocated", "1 smaller prefix"],
    ]);
    expect(tiles).toContainEqual(
      expect.objectContaining({
        kind: "aggregate-allocated",
        addressCount: 1n,
        members: [expect.objectContaining({ cidr: "10.3.0.1/32" })],
      })
    );
    expect(countOverlappingRanges(tiles)).toBe(0);
  });

  it("collapses free blocks below 1/4096 of the parent into one smaller-free-blocks tile", () => {
    // GIVEN
    const parent = generateTreeMapParent({ cidr: "10.0.0.0/8" });
    const children = [generateTreeMapChild({ cidr: "10.0.0.0/9" })];
    const freeBlocks = ["10.128.0.0/10", "10.192.0.0/24", "10.192.1.0/24", "10.192.2.0/23"].map(
      (cidr) => generateTreeMapFreeBlock({ cidr })
    );

    // WHEN
    const tiles = buildTreeMapTiles({ parent, children, freeBlocks, totalChildCount: 1 });

    // THEN
    expect(tiles.map((tile) => [tile.kind, tile.label])).toEqual([
      ["allocated", "10.0.0.0/9"],
      ["free", "10.128.0.0/10"],
      ["aggregate-free", "3 smaller free blocks"],
    ]);
    expect(tiles).toContainEqual(
      expect.objectContaining({ kind: "aggregate-free", addressCount: 1024n })
    );
    expect(countOverlappingRanges(tiles)).toBe(0);
  });

  it("sizes the remainder tile to the parent minus every other tile when children are capped", () => {
    // GIVEN
    const parent = generateTreeMapParent({ cidr: "10.0.0.0/8" });
    const children = generateSlash18ChildrenOfDemoSupernet(1000);

    // WHEN
    const tiles = buildTreeMapTiles({ parent, children, freeBlocks: [], totalChildCount: 1200 });

    // THEN
    const remainderTiles = tiles.filter((tile) => tile.kind === "remainder");
    const otherTiles = tiles.filter((tile) => tile.kind !== "remainder");
    expect(remainderTiles).toEqual([
      expect.objectContaining({
        label: "200 more children",
        hiddenChildCount: 200,
        addressCount: 2n ** 24n - sumAddressCounts(otherTiles),
      }),
    ]);
    expect(otherTiles).toHaveLength(1000);
    expect(sumAddressCounts(tiles)).toBe(2n ** 24n);
    expect(countOverlappingRanges(tiles)).toBe(0);
  });

  it("aggregates both a /48 and a /64 inside an IPv6 /32 as they fall below 1/4096", () => {
    // GIVEN
    const parent = generateTreeMapParent({ cidr: "2001:db8::/32" });
    const children = ["2001:db8:1::/48", "2001:db8:2:3::/64"].map((cidr) =>
      generateTreeMapChild({ cidr })
    );

    // WHEN
    const tiles = buildTreeMapTiles({ parent, children, freeBlocks: [], totalChildCount: 2 });

    // THEN
    expect(tiles).toEqual([
      expect.objectContaining({
        kind: "aggregate-allocated",
        label: "2 smaller prefixes",
        addressCount: 2n ** 80n + 2n ** 64n,
        members: children,
      }),
    ]);
    expect(countOverlappingRanges(tiles)).toBe(0);
  });

  it("keeps an IPv6 child exactly at 1/4096 of its parent as an allocated tile", () => {
    // GIVEN
    const parent = generateTreeMapParent({ cidr: "2001:db8::/32" });
    const children = ["2001:db8:10::/44", "2001:db8:2:3::/64"].map((cidr) =>
      generateTreeMapChild({ cidr })
    );

    // WHEN
    const tiles = buildTreeMapTiles({ parent, children, freeBlocks: [], totalChildCount: 2 });

    // THEN
    expect(tiles.map((tile) => [tile.kind, tile.label, tile.weight])).toEqual([
      ["allocated", "2001:db8:10::/44", 1 / 4096],
      ["aggregate-allocated", "1 smaller prefix", 2 ** -32],
    ]);
    expect(countOverlappingRanges(tiles)).toBe(0);
  });

  it("aggregates a /128 inside a /32 while the address counts still sum to the parent", () => {
    // GIVEN
    const parent = generateTreeMapParent({ cidr: "2001:db8::/32" });
    const children = [generateTreeMapChild({ cidr: "2001:db8::/128" })];
    const freeBlocks = generateFreeBlocksAroundFirstIpv6Address();

    // WHEN
    const tiles = buildTreeMapTiles({ parent, children, freeBlocks, totalChildCount: 1 });

    // THEN
    expect(tiles.map((tile) => [tile.kind, tile.label])).toEqual([
      ["free", "2001:db8:8000:0:0:0:0:0/33"],
      ["free", "2001:db8:4000:0:0:0:0:0/34"],
      ["free", "2001:db8:2000:0:0:0:0:0/35"],
      ["free", "2001:db8:1000:0:0:0:0:0/36"],
      ["free", "2001:db8:800:0:0:0:0:0/37"],
      ["free", "2001:db8:400:0:0:0:0:0/38"],
      ["free", "2001:db8:200:0:0:0:0:0/39"],
      ["free", "2001:db8:100:0:0:0:0:0/40"],
      ["free", "2001:db8:80:0:0:0:0:0/41"],
      ["free", "2001:db8:40:0:0:0:0:0/42"],
      ["free", "2001:db8:20:0:0:0:0:0/43"],
      ["free", "2001:db8:10:0:0:0:0:0/44"],
      ["aggregate-free", "84 smaller free blocks"],
      ["aggregate-allocated", "1 smaller prefix"],
    ]);
    expect(sumAddressCounts(tiles)).toBe(2n ** 96n);
    expect(countOverlappingRanges(tiles)).toBe(0);
  });
});
