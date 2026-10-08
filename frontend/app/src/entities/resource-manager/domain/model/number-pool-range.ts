/** A range as typed in the form; `rangeId` is set when the row exists on the server. */
export interface RangeRow {
  rangeId?: string;
  start: string;
  end: string;
  weight: string;
}

export interface StoredRange {
  id: string;
  start: number;
  end: number;
  weight: number | null;
}

export interface RangeUpdate {
  id: string;
  start: number;
  end: number;
  weight: number | null;
}

export interface RangeInput {
  start: number;
  end: number;
  weight: number | null;
}

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
