import { describe, expect, it } from "vitest";

import type {
  TreeMapRect,
  TreeMapTile,
} from "@/entities/ipam/ip-prefixes/domain/model/ip-prefix-tree-map";
import { layoutTreeMap } from "@/entities/ipam/ip-prefixes/domain/rules/layout-tree-map";

import { generateAllocatedTile } from "../../../../../../tests/fake/ip-prefix-tree-map";

const TOLERANCE = 1e-6;

// A fixed-seed generator keeps the "random" case reproducible across runs.
function seededWeights(count: number, seed: number): number[] {
  const raw: number[] = [];
  let state = seed;
  for (let index = 0; index < count; index += 1) {
    state = (state * 1_103_515_245 + 12_345) % 2_147_483_648;
    raw.push(state / 2_147_483_648 + 0.01);
  }
  const total = raw.reduce((sum, value) => sum + value, 0);
  return raw.map((value) => value / total).sort((left, right) => right - left);
}

function tilesFromWeights(weights: number[]): TreeMapTile[] {
  return weights.map((weight, index) =>
    generateAllocatedTile({ weight, child: { cidr: `10.${index}.0.0/16` } })
  );
}

function isInsideContainer(rect: TreeMapRect): boolean {
  return (
    rect.x >= -TOLERANCE &&
    rect.y >= -TOLERANCE &&
    rect.x + rect.width <= 100 + TOLERANCE &&
    rect.y + rect.height <= 100 + TOLERANCE
  );
}

function overlaps(left: TreeMapRect, right: TreeMapRect): boolean {
  const separatedHorizontally =
    left.x + left.width <= right.x + TOLERANCE || right.x + right.width <= left.x + TOLERANCE;
  const separatedVertically =
    left.y + left.height <= right.y + TOLERANCE || right.y + right.height <= left.y + TOLERANCE;
  return !separatedHorizontally && !separatedVertically;
}

function overlappingPairs(rects: TreeMapRect[]): Array<[string, string]> {
  const pairs: Array<[string, string]> = [];
  rects.forEach((left, leftIndex) => {
    rects.slice(leftIndex + 1).forEach((right) => {
      if (overlaps(left, right)) pairs.push([left.tile.key, right.tile.key]);
    });
  });
  return pairs;
}

const CASES = [
  { name: "weights 0.5, 0.25 and 0.25", weights: [0.5, 0.25, 0.25] },
  { name: "a single tile", weights: [1] },
  { name: "twenty random weights", weights: seededWeights(20, 42) },
];

describe.each([1, 2])("layoutTreeMap at aspect ratio %d", (aspectRatio) => {
  it.each(CASES)("keeps every rect inside the container for $name", ({ weights }) => {
    // GIVEN
    const tiles = tilesFromWeights(weights);

    // WHEN
    const rects = layoutTreeMap(tiles, aspectRatio);

    // THEN
    expect(rects.filter((rect) => !isInsideContainer(rect))).toEqual([]);
  });

  it.each(CASES)("never overlaps two rects for $name", ({ weights }) => {
    // GIVEN
    const tiles = tilesFromWeights(weights);

    // WHEN
    const rects = layoutTreeMap(tiles, aspectRatio);

    // THEN
    expect(overlappingPairs(rects)).toEqual([]);
  });

  it.each(CASES)("sizes each rect's area to its tile weight for $name", ({ weights }) => {
    // GIVEN
    const tiles = tilesFromWeights(weights);

    // WHEN
    const rects = layoutTreeMap(tiles, aspectRatio);

    // THEN
    const areaErrors = rects.map((rect) =>
      Math.abs((rect.width * rect.height) / 10_000 - rect.tile.weight)
    );
    expect(areaErrors.filter((error) => error > TOLERANCE)).toEqual([]);
  });

  it.each(CASES)("returns one rect per tile in the input order for $name", ({ weights }) => {
    // GIVEN
    const tiles = tilesFromWeights(weights);

    // WHEN
    const rects = layoutTreeMap(tiles, aspectRatio);

    // THEN
    expect(rects.map((rect) => rect.tile)).toEqual(tiles);
  });
});

describe("layoutTreeMap", () => {
  it("returns no rects for no tiles", () => {
    // GIVEN
    const tiles: TreeMapTile[] = [];

    // WHEN
    const rects = layoutTreeMap(tiles, 2);

    // THEN
    expect(rects).toEqual([]);
  });

  it("gives a zero-weight tile a zero-size rect", () => {
    // GIVEN
    const tiles = tilesFromWeights([1, 0]);

    // WHEN
    const rects = layoutTreeMap(tiles, 2);

    // THEN
    expect(rects.map((rect) => [rect.width, rect.height])).toEqual([
      [100, 100],
      [0, 0],
    ]);
  });

  it("splits two equal tiles across the longer side of a 2:1 container", () => {
    // GIVEN
    const tiles = tilesFromWeights([0.5, 0.5]);

    // WHEN
    const rects = layoutTreeMap(tiles, 2);

    // THEN
    expect(rects.map(({ x, y, width, height }) => ({ x, y, width, height }))).toEqual([
      { x: 0, y: 0, width: 50, height: 100 },
      { x: 50, y: 0, width: 50, height: 100 },
    ]);
  });
});
