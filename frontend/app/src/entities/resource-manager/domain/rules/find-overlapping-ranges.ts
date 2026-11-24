export interface RangeBounds {
  start: number;
  end: number;
}

export function findOverlappingRanges<Key>(
  ranges: ReadonlyArray<RangeBounds & { key: Key }>
): Map<Key, Array<RangeBounds>> {
  const overlaps = new Map<Key, Array<RangeBounds>>();

  for (const range of ranges) {
    const others = ranges
      .filter((other) => other !== range && range.start <= other.end && other.start <= range.end)
      .map(({ start, end }) => ({ start, end }));

    if (others.length > 0) overlaps.set(range.key, others);
  }

  return overlaps;
}
