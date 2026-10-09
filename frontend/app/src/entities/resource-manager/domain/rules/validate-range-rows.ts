import { formatNumberDisplay } from "@/shared/utils/number";

import type {
  RangeRow,
  RangeRowErrors,
} from "@/entities/resource-manager/domain/model/number-pool-range";

export interface RangeLimits {
  attribute: string;
  min?: number | null;
  max?: number | null;
}

export function parseWholeNumber(value: string): bigint | null {
  const trimmed = value.trim();
  return /^-?\d+$/.test(trimmed) ? BigInt(trimmed) : null;
}

export function parseWeight(value: string): number | null {
  const parsed = parseWholeNumber(value);
  if (parsed === null || parsed < 0n || parsed > BigInt(Number.MAX_SAFE_INTEGER)) return null;
  return Number(parsed);
}

export function formatRange(start: bigint, end: bigint): string {
  return `${formatNumberDisplay(start)} – ${formatNumberDisplay(end)}`;
}

function parseBounds(row: RangeRow): { start: bigint; end: bigint } | null {
  const start = parseWholeNumber(row.start);
  const end = parseWholeNumber(row.end);
  if (start === null || end === null || end < start) return null;

  return { start, end };
}

function getBoundError(value: string): string | undefined {
  if (value.trim() === "") return "Required";
  if (parseWholeNumber(value) === null) return "Whole number";
  return undefined;
}

function getRowErrors(row: RangeRow): RangeRowErrors {
  const errors: RangeRowErrors = {};

  const startError = getBoundError(row.start);
  if (startError) errors.start = startError;

  const endError = getBoundError(row.end);
  if (endError) {
    errors.end = endError;
  } else if (!startError && parseBounds(row) === null) {
    errors.end = "Must not be lower than start";
  }

  if (row.weight.trim() !== "" && parseWeight(row.weight) === null) {
    errors.weight = "Whole number of 0 or more";
  }

  return errors;
}

export function validateRangeRows(rows: RangeRow[]): Record<number, RangeRowErrors> {
  const errors: Record<number, RangeRowErrors> = {};

  rows.forEach((row, index) => {
    const rowErrors = getRowErrors(row);
    if (Object.keys(rowErrors).length > 0) errors[index] = rowErrors;
  });

  const bounded = rows.flatMap((row, index) => {
    const bounds = parseBounds(row);
    return bounds ? [{ index, ...bounds }] : [];
  });

  for (let i = 0; i < bounded.length; i++) {
    for (let j = i + 1; j < bounded.length; j++) {
      const a = bounded[i]!;
      const b = bounded[j]!;
      if (a.start <= b.end && b.start <= a.end) {
        errors[a.index] = { ...errors[a.index], row: `Overlaps ${formatRange(b.start, b.end)}` };
        errors[b.index] = { ...errors[b.index], row: `Overlaps ${formatRange(a.start, a.end)}` };
      }
    }
  }

  return errors;
}

export function getRangeClipHint(
  row: RangeRow,
  limits: RangeLimits | null | undefined
): string | null {
  if (!limits) return null;

  const bounds = parseBounds(row);
  if (!bounds) return null;

  const lowest = limits.min == null ? bounds.start : BigInt(limits.min);
  const highest = limits.max == null ? bounds.end : BigInt(limits.max);
  const start = bounds.start > lowest ? bounds.start : lowest;
  const end = bounds.end < highest ? bounds.end : highest;
  if (start === bounds.start && end === bounds.end) return null;

  if (start > end) {
    return `Outside the ${limits.attribute} limits, so no number can come from it`;
  }

  return `Clipped to ${formatRange(start, end)} by the ${limits.attribute} limits`;
}
