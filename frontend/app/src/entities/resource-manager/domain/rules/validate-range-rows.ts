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

export function parseWholeNumber(value: string): number | null {
  const trimmed = value.trim();
  if (!/^-?\d+$/.test(trimmed)) return null;

  const parsed = Number(trimmed);
  return Number.isSafeInteger(parsed) ? parsed : null;
}

export function formatRange(start: number, end: number): string {
  return `${formatNumberDisplay(start)} – ${formatNumberDisplay(end)}`;
}

function parseBounds(row: RangeRow): { start: number; end: number } | null {
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

  if (row.weight.trim() !== "") {
    const weight = parseWholeNumber(row.weight);
    if (weight === null || weight < 0) errors.weight = "Whole number of 0 or more";
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

  const min = limits.min ?? Number.NEGATIVE_INFINITY;
  const max = limits.max ?? Number.POSITIVE_INFINITY;
  if (bounds.start >= min && bounds.end <= max) return null;

  if (bounds.end < min || bounds.start > max) {
    return `Outside the ${limits.attribute} limits, so no number can come from it`;
  }

  const clipped = formatRange(Math.max(bounds.start, min), Math.min(bounds.end, max));
  return `Clipped to ${clipped} by the ${limits.attribute} limits`;
}
