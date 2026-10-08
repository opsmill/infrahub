/** A range as typed in the form; `rangeId` is set when the row exists on the server. */
export interface RangeRow {
  rangeId?: string;
  start: string;
  end: string;
  weight: string;
}

// Rows hold the plain typed strings rather than `{ source, value }` because a range is a peer node of the pool, not an attribute with a provenance.
export const EMPTY_RANGE_ROW: RangeRow = { start: "", end: "", weight: "" };

export interface StoredRange {
  id: string;
  start: bigint;
  end: bigint;
  weight: number | null;
}

export type RangeUpdate = StoredRange;

export type RangeInput = Omit<StoredRange, "id">;

export interface RangeChanges {
  deletes: string[];
  smaller: RangeUpdate[];
  larger: RangeUpdate[];
  creates: RangeInput[];
}

export interface RangeRowErrors {
  start?: string;
  end?: string;
  weight?: string;
  row?: string;
}

export interface NumberPoolForEditing {
  id: string;
  name: string;
  description: string;
  node: string;
  nodeAttribute: string;
  allocationScope: string[];
  poolType: "User" | "Schema";
  ranges: StoredRange[];
}
