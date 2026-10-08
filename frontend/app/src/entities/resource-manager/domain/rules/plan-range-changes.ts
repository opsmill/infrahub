import type {
  RangeChanges,
  RangeInput,
  RangeRow,
  StoredRange,
} from "@/entities/resource-manager/domain/model/number-pool-range";
import { parseWholeNumber } from "@/entities/resource-manager/domain/rules/validate-range-rows";

export function sortStoredRanges(ranges: StoredRange[]): StoredRange[] {
  return [...ranges].sort((a, b) => {
    if (a.weight !== b.weight) {
      if (a.weight === null) return 1;
      if (b.weight === null) return -1;
      return b.weight - a.weight;
    }
    return a.start - b.start;
  });
}

function toRangeInput(row: RangeRow): RangeInput {
  return {
    start: parseWholeNumber(row.start)!,
    end: parseWholeNumber(row.end)!,
    weight: row.weight.trim() === "" ? null : parseWholeNumber(row.weight),
  };
}

/** Expects rows without validation errors. */
export function diffRanges(stored: StoredRange[], rows: RangeRow[]): RangeChanges {
  const storedById = new Map(stored.map((range) => [range.id, range]));
  const linkedIds = new Set(rows.flatMap((row) => (row.rangeId ? [row.rangeId] : [])));
  const changes: RangeChanges = {
    deletes: stored.filter((range) => !linkedIds.has(range.id)).map((range) => range.id),
    smaller: [],
    larger: [],
    creates: [],
  };

  for (const row of rows) {
    const input = toRangeInput(row);
    const previous = row.rangeId ? storedById.get(row.rangeId) : undefined;

    if (!previous) {
      changes.creates.push(input);
      continue;
    }

    const isUnchanged =
      input.start === previous.start &&
      input.end === previous.end &&
      input.weight === previous.weight;
    if (isUnchanged) continue;

    const update = { id: previous.id, ...input };
    if (input.start >= previous.start && input.end <= previous.end) {
      changes.smaller.push(update);
    } else {
      changes.larger.push(update);
    }
  }

  return changes;
}

export function matchRowsToStored(rows: RangeRow[], stored: StoredRange[]): RangeRow[] {
  const linkedIds = new Set(rows.flatMap((row) => (row.rangeId ? [row.rangeId] : [])));

  return rows.map((row) => {
    if (row.rangeId) return row;

    const start = parseWholeNumber(row.start);
    const end = parseWholeNumber(row.end);
    const match = stored.find(
      (range) => !linkedIds.has(range.id) && range.start === start && range.end === end
    );
    if (!match) return row;

    linkedIds.add(match.id);
    return { ...row, rangeId: match.id };
  });
}
