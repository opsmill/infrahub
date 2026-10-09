import type { NumberPoolRange } from "@/entities/resource-manager/domain/model/number-pool";

/** Orders ranges the way the pool allocates from them: highest weight first, then lowest start. */
export const sortRangesByFillOrder = (ranges: NumberPoolRange[]): NumberPoolRange[] =>
  [...ranges].sort(
    (a, b) =>
      b.allocation_weight.value - a.allocation_weight.value ||
      a.start.value - b.start.value ||
      a.end.value - b.end.value
  );
