import { describe, expect, it } from "vitest";

import type { TreeMapRect } from "@/entities/ipam/ip-prefixes/domain/model/ip-prefix-tree-map";
import { layoutTreeMap } from "@/entities/ipam/ip-prefixes/domain/rules/layout-tree-map";

import {
  generateAllocatedTile,
  generateFreeTile,
  generateTreeMapParent,
  sizeOf,
} from "../../../../../../tests/fake/ip-prefix-tree-map";

const PARENT = generateTreeMapParent({ cidr: "10.0.0.0/16" });

const EPSILON = 1e-9;

const touches = (left: TreeMapRect, right: TreeMapRect): boolean => {
  const sharesVerticalEdge =
    (Math.abs(left.x + left.width - right.x) < EPSILON ||
      Math.abs(right.x + right.width - left.x) < EPSILON) &&
    left.y < right.y + right.height - EPSILON &&
    right.y < left.y + left.height - EPSILON;
  const sharesHorizontalEdge =
    (Math.abs(left.y + left.height - right.y) < EPSILON ||
      Math.abs(right.y + right.height - left.y) < EPSILON) &&
    left.x < right.x + right.width - EPSILON &&
    right.x < left.x + left.width - EPSILON;
  return sharesVerticalEdge || sharesHorizontalEdge;
};

const overlaps = (left: TreeMapRect, right: TreeMapRect): boolean =>
  left.x < right.x + right.width - EPSILON &&
  right.x < left.x + left.width - EPSILON &&
  left.y < right.y + right.height - EPSILON &&
  right.y < left.y + left.height - EPSILON;

describe("layoutTreeMap", () => {
  it("gives every block an area equal to its share of the parent", () => {
    // GIVEN blocks of three different sizes inside the /16
    const tiles = ["10.0.0.0/17", "10.0.128.0/18", "10.0.192.0/20"].map((cidr) =>
      generateAllocatedTile({ child: { cidr } })
    );

    // WHEN they are laid out
    const rects = layoutTreeMap(tiles, PARENT.size);

    // THEN each rectangle's area in percent squared matches 10,000 times its share
    const shares = rects.map((rect) => (rect.width * rect.height) / 10_000);
    expect(shares[0]).toBeCloseTo(1 / 2, 9);
    expect(shares[1]).toBeCloseTo(1 / 4, 9);
    expect(shares[2]).toBeCloseTo(1 / 16, 9);
  });

  it("keeps every rectangle inside the container and no two overlapping", () => {
    // GIVEN every /20 of the /16 as a tile
    const tiles = Array.from({ length: 16 }, (_, index) =>
      generateAllocatedTile({ child: { cidr: `10.0.${index * 16}.0/20` } })
    );

    // WHEN they are laid out
    const rects = layoutTreeMap(tiles, PARENT.size);

    // THEN they tile the unit square without overlap
    for (const rect of rects) {
      expect(rect.x).toBeGreaterThanOrEqual(-EPSILON);
      expect(rect.y).toBeGreaterThanOrEqual(-EPSILON);
      expect(rect.x + rect.width).toBeLessThanOrEqual(100 + EPSILON);
      expect(rect.y + rect.height).toBeLessThanOrEqual(100 + EPSILON);
    }
    for (const [index, rect] of rects.entries()) {
      for (const other of rects.slice(index + 1)) {
        expect(overlaps(rect, other), `${rect.tile.key} overlaps ${other.tile.key}`).toBe(false);
      }
    }
  });

  it("places two adjacent free blocks as touching rectangles", () => {
    // GIVEN two free blocks that are consecutive in address space
    const tiles = [
      generateFreeTile({ block: { cidr: "10.0.64.0/18" } }),
      generateFreeTile({ block: { cidr: "10.0.128.0/18" } }),
    ];

    // WHEN they are laid out
    const [left, right] = layoutTreeMap(tiles, PARENT.size);

    // THEN they share an edge
    expect(left && right && touches(left, right)).toBe(true);
  });

  it("places every pair of consecutive same-size blocks as touching rectangles", () => {
    // GIVEN all 64 /22 blocks of the /16, in address order
    const tiles = Array.from({ length: 64 }, (_, index) =>
      generateFreeTile({ block: { cidr: `10.0.${index * 4}.0/22` } })
    );

    // WHEN they are laid out
    const rects = layoutTreeMap(tiles, PARENT.size);

    // THEN each block touches the next one along the address order
    for (let index = 0; index + 1 < rects.length; index += 1) {
      const current = rects[index];
      const next = rects[index + 1];
      expect(
        current && next && touches(current, next),
        `${current?.tile.key} and ${next?.tile.key}`
      ).toBe(true);
    }
  });

  it("places an odd-depth block as the union of its two halves", () => {
    // GIVEN a /17 (one bit below the parent) and its two /18 halves
    const whole = layoutTreeMap(
      [generateAllocatedTile({ child: { cidr: "10.0.0.0/17" } })],
      PARENT.size
    )[0];
    const halves = layoutTreeMap(
      ["10.0.0.0/18", "10.0.64.0/18"].map((cidr) => generateFreeTile({ block: { cidr } })),
      PARENT.size
    );

    // WHEN the bounding box of the halves is compared with the whole
    const minX = Math.min(...halves.map((rect) => rect.x));
    const minY = Math.min(...halves.map((rect) => rect.y));
    const maxX = Math.max(...halves.map((rect) => rect.x + rect.width));
    const maxY = Math.max(...halves.map((rect) => rect.y + rect.height));

    // THEN they coincide
    expect(whole?.x).toBeCloseTo(minX, 9);
    expect(whole?.y).toBeCloseTo(minY, 9);
    expect(whole && whole.x + whole.width).toBeCloseTo(maxX, 9);
    expect(whole && whole.y + whole.height).toBeCloseTo(maxY, 9);
  });

  it("gives the parent itself the whole container", () => {
    // GIVEN a tile covering the parent block
    const tiles = [generateFreeTile({ block: { cidr: "10.0.0.0/16" } })];

    // WHEN it is laid out
    const [rect] = layoutTreeMap(tiles, PARENT.size);

    // THEN it fills the container
    expect(rect).toMatchObject({ x: 0, y: 0, width: 100, height: 100 });
  });

  it("lays out IPv6 blocks far below the parent without losing precision", () => {
    // GIVEN a /64 and the /64 next to it inside a /32
    const parent = sizeOf("2001:db8::/32");
    const tiles = ["2001:db8:0:0::/64", "2001:db8:0:1::/64"].map((cidr) =>
      generateFreeTile({ block: { cidr } })
    );

    // WHEN they are laid out
    const [first, second] = layoutTreeMap(tiles, parent);

    // THEN both are inside the container, tiny, and touching
    expect(first && second && touches(first, second)).toBe(true);
    expect(first?.width).toBeCloseTo(100 / 2 ** 16, 12);
  });
});
