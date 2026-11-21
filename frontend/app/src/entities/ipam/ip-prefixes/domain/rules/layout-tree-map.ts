import type {
  PrefixSize,
  TreeMapRect,
  TreeMapTile,
} from "@/entities/ipam/ip-prefixes/domain/model/ip-prefix-tree-map";

interface Cell {
  x: bigint;
  y: bigint;
}

/** Maps index `d` along a Hilbert curve of the given order to its cell on a 2^order square grid. */
function hilbertCell(order: number, d: bigint): Cell {
  const side = 2n ** BigInt(order);
  let x = 0n;
  let y = 0n;
  let t = d;
  for (let s = 1n; s < side; s *= 2n) {
    const rx = (t / 2n) % 2n;
    const ry = (t + rx) % 2n;
    if (ry === 0n) {
      if (rx === 1n) {
        x = s - 1n - x;
        y = s - 1n - y;
      }
      [x, y] = [y, x];
    }
    x += s * rx;
    y += s * ry;
    t /= 4n;
  }
  return { x, y };
}

interface Box {
  x: number;
  y: number;
  width: number;
  height: number;
}

function boundingBox(cells: Cell[], side: bigint): Box {
  const xs = cells.map((cell) => cell.x);
  const ys = cells.map((cell) => cell.y);
  const minX = xs.reduce((min, x) => (x < min ? x : min));
  const minY = ys.reduce((min, y) => (y < min ? y : min));
  const maxX = xs.reduce((max, x) => (x > max ? x : max));
  const maxY = ys.reduce((max, y) => (y > max ? y : max));
  const scale = 100 / Number(side);
  return {
    x: Number(minX) * scale,
    y: Number(minY) * scale,
    width: Number(maxX - minX + 1n) * scale,
    height: Number(maxY - minY + 1n) * scale,
  };
}

/**
 * Places one block of the parent on the unit square. The bits below the parent's length index
 * the block along a Hilbert curve: an even number of bits is one curve cell, an odd number is
 * two consecutive cells, which the curve keeps side by side.
 */
function placeBlock(parent: PrefixSize, block: PrefixSize): Box {
  const depth = block.prefixLength - parent.prefixLength;
  if (depth <= 0) return { x: 0, y: 0, width: 100, height: 100 };

  const offset = (block.networkAddress - parent.networkAddress) / block.addressCount;
  const order = Math.ceil(depth / 2);
  const side = 2n ** BigInt(order);
  const cells =
    depth % 2 === 0
      ? [hilbertCell(order, offset)]
      : [hilbertCell(order, offset * 2n), hilbertCell(order, offset * 2n + 1n)];
  return boundingBox(cells, side);
}

/**
 * Lays tiles out by address: each tile takes the rectangle of its block on a Hilbert curve over
 * the parent, so blocks that are adjacent in address space share an edge and contiguous free
 * space reads as one region. Coordinates are percentages of the container.
 */
export function layoutTreeMap(tiles: TreeMapTile[], parent: PrefixSize): TreeMapRect[] {
  return tiles.map((tile) => ({ tile, ...placeBlock(parent, tile.size) }));
}
