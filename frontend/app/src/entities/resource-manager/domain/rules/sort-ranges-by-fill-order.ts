import type { NumberPoolRange } from "@/entities/resource-manager/domain/model/number-pool";

const endOf = (range: NumberPoolRange) => range.end.value ?? Number.POSITIVE_INFINITY;

const compareEnds = (a: NumberPoolRange, b: NumberPoolRange) => {
  const [endA, endB] = [endOf(a), endOf(b)];
  if (endA === endB) return 0;
  return endA < endB ? -1 : 1;
};

/** Orders ranges the way the pool allocates from them: highest weight first, then lowest start. */
export const sortRangesByFillOrder = (ranges: NumberPoolRange[]): NumberPoolRange[] =>
  [...ranges].sort(
    (a, b) =>
      b.allocation_weight.value - a.allocation_weight.value ||
      a.start.value - b.start.value ||
      compareEnds(a, b)
  );
