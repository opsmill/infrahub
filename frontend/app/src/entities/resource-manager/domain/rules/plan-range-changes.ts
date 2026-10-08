import type {
  RangeChanges,
  RangeInput,
  RangeRow,
  RangeUpdate,
  StoredRange,
} from "@/entities/resource-manager/domain/model/number-pool-range";
import {
  parseWeight,
  parseWholeNumber,
} from "@/entities/resource-manager/domain/rules/validate-range-rows";

function compareStart(a: StoredRange, b: StoredRange): number {
  if (a.start === b.start) return 0;
  return a.start < b.start ? -1 : 1;
}

export function sortStoredRanges(ranges: StoredRange[]): StoredRange[] {
  return [...ranges].sort((a, b) => (b.weight ?? 0) - (a.weight ?? 0) || compareStart(a, b));
}

export function toRangeRows(ranges: StoredRange[]): RangeRow[] {
  return sortStoredRanges(ranges).map((range) => ({
    rangeId: range.id,
    start: String(range.start),
    end: String(range.end),
    weight: range.weight === null ? "" : String(range.weight),
  }));
}

export function hasRangeChanges(changes: RangeChanges): boolean {
  return Object.values(changes).some((group) => group.length > 0);
}

function toRangeInput(row: RangeRow): RangeInput {
  return {
    start: parseWholeNumber(row.start)!,
    end: parseWholeNumber(row.end)!,
    weight: row.weight.trim() === "" ? null : parseWeight(row.weight),
  };
}

function overlaps(a: RangeInput, b: RangeInput): boolean {
  return a.start <= b.end && b.start <= a.end;
}

/**
 * Orders updates so that one is sent after every other update whose old bounds it takes, because the
 * backend checks each call against the stored ranges; updates that take each other's bounds keep their order.
 */
function orderLargerUpdates(
  updates: RangeUpdate[],
  storedById: Map<string, StoredRange>
): RangeUpdate[] {
  const pending = [...updates];
  const ordered: RangeUpdate[] = [];

  while (pending.length > 0) {
    const readyIndex = pending.findIndex((update) =>
      pending.every((other) => other === update || !overlaps(update, storedById.get(other.id)!))
    );
    ordered.push(...pending.splice(Math.max(readyIndex, 0), 1));
  }

  return ordered;
}

/**
 * Expects rows without validation errors. Deletes only the known ranges that no row links to, so a range
 * added elsewhere after the rows were loaded is kept.
 */
export function diffRanges(
  stored: StoredRange[],
  rows: RangeRow[],
  knownRangeIds: ReadonlySet<string>
): RangeChanges {
  const storedById = new Map(stored.map((range) => [range.id, range]));
  const linkedIds = new Set(rows.flatMap((row) => (row.rangeId ? [row.rangeId] : [])));
  const changes: RangeChanges = {
    deletes: stored
      .filter((range) => knownRangeIds.has(range.id) && !linkedIds.has(range.id))
      .map((range) => range.id),
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

  changes.larger = orderLargerUpdates(changes.larger, storedById);
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
