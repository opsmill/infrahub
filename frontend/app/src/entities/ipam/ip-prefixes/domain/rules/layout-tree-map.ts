import type {
  TreeMapRect,
  TreeMapTile,
} from "@/entities/ipam/ip-prefixes/domain/model/ip-prefix-tree-map";

interface Box {
  x: number;
  y: number;
  width: number;
  height: number;
}

interface Entry {
  tile: TreeMapTile;
  area: number;
}

interface Placed {
  tile: TreeMapTile;
  box: Box;
}

function sumAreas(entries: Entry[]): number {
  return entries.reduce((sum, entry) => sum + entry.area, 0);
}

function worstAspectRatio(entries: Entry[], side: number): number {
  const total = sumAreas(entries);
  if (total === 0 || side === 0) return Number.POSITIVE_INFINITY;

  const sideSquared = side * side;
  const totalSquared = total * total;
  return entries.reduce(
    (worst, { area }) =>
      Math.max(worst, (sideSquared * area) / totalSquared, totalSquared / (sideSquared * area)),
    0
  );
}

function rowLength(entries: Entry[], side: number): number {
  let length = 1;
  while (length < entries.length) {
    const current = worstAspectRatio(entries.slice(0, length), side);
    const extended = worstAspectRatio(entries.slice(0, length + 1), side);
    if (extended > current) break;
    length += 1;
  }
  return length;
}

function layoutRow(row: Entry[], box: Box): { placed: Placed[]; rest: Box } {
  const total = sumAreas(row);

  if (box.width >= box.height) {
    const stripWidth = total / box.height;
    let y = box.y;
    const placed = row.map(({ tile, area }) => {
      const height = area / stripWidth;
      const placedBox = { x: box.x, y, width: stripWidth, height };
      y += height;
      return { tile, box: placedBox };
    });
    const rest = { ...box, x: box.x + stripWidth, width: box.width - stripWidth };
    return { placed, rest };
  }

  const stripHeight = total / box.width;
  let x = box.x;
  const placed = row.map(({ tile, area }) => {
    const width = area / stripHeight;
    const placedBox = { x, y: box.y, width, height: stripHeight };
    x += width;
    return { tile, box: placedBox };
  });
  const rest = { ...box, y: box.y + stripHeight, height: box.height - stripHeight };
  return { placed, rest };
}

function squarify(entries: Entry[], container: Box): Placed[] {
  const placed: Placed[] = [];
  let box = container;
  let remaining = entries;

  while (remaining.length > 0) {
    const [head] = remaining;
    if (head === undefined) break;

    const side = Math.min(box.width, box.height);
    if (side <= 0 || head.area <= 0) {
      placed.push({ tile: head.tile, box: { x: box.x, y: box.y, width: 0, height: 0 } });
      remaining = remaining.slice(1);
      continue;
    }

    const length = rowLength(remaining, side);
    const row = layoutRow(remaining.slice(0, length), box);
    placed.push(...row.placed);
    box = row.rest;
    remaining = remaining.slice(length);
  }

  return placed;
}

/**
 * Lays tiles out as a squarified treemap inside an `aspectRatio` by 1 box and returns one
 * rectangle per tile, in input order, as percentages of the container. Tiles are expected in
 * descending weight order; a zero-weight tile gets a zero-size rectangle.
 */
export function layoutTreeMap(tiles: TreeMapTile[], aspectRatio: number): TreeMapRect[] {
  const totalWeight = tiles.reduce((sum, tile) => sum + tile.weight, 0);
  const entries = tiles.map((tile) => ({
    tile,
    area: totalWeight > 0 ? (Math.max(tile.weight, 0) / totalWeight) * aspectRatio : 0,
  }));

  const placed = squarify(entries, { x: 0, y: 0, width: aspectRatio, height: 1 });

  return placed.map(({ tile, box }) => ({
    tile,
    x: (box.x / aspectRatio) * 100,
    y: box.y * 100,
    width: (box.width / aspectRatio) * 100,
    height: box.height * 100,
  }));
}
