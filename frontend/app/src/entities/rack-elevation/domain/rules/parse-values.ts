import type { RackFace } from "@/entities/rack-elevation/domain/model/elevation";
import type {
  AttributeValue,
  SchemaAttribute,
} from "@/entities/rack-elevation/domain/model/schema";

const NUMBER_PATTERN = /-?\d+(\.\d+)?/;
const TRUE_VALUES = new Set(["true", "yes", "1", "full"]);

export function parseNumber(value: AttributeValue): number | null {
  if (typeof value === "number") return Number.isFinite(value) ? value : null;
  if (typeof value !== "string") return null;
  const match = value.match(NUMBER_PATTERN);
  return match ? Number(match[0]) : null;
}

export function parseBoolean(value: AttributeValue): boolean {
  if (typeof value === "boolean") return value;
  if (value === null) return false;
  return TRUE_VALUES.has(String(value).trim().toLowerCase());
}

export function splitValues(values: string): string[] {
  return values
    .split(",")
    .map((value) => value.trim().toLowerCase())
    .filter(Boolean);
}

export function parseFace(
  value: AttributeValue,
  frontValues: string,
  rearValues: string
): RackFace | null {
  if (value === null) return null;
  const normalized = String(value).trim().toLowerCase();
  if (splitValues(frontValues).includes(normalized)) return "front";
  if (splitValues(rearValues).includes(normalized)) return "rear";
  return null;
}

/** Keeps the original format of text values, so "U12" becomes "U14" rather than 14. */
export function formatNumberLike(previous: AttributeValue, next: number): AttributeValue {
  if (typeof previous === "string" && NUMBER_PATTERN.test(previous)) {
    return previous.replace(NUMBER_PATTERN, String(next));
  }
  return next;
}

export function formatFace(
  face: RackFace,
  previous: AttributeValue,
  frontValues: string,
  rearValues: string,
  attribute: SchemaAttribute | undefined
): AttributeValue {
  const candidate = splitValues(face === "front" ? frontValues : rearValues)[0] ?? face;
  const choice = attribute?.choices?.find((option) => option.toLowerCase() === candidate);
  if (choice) return choice;
  const isUpperCase = typeof previous === "string" && previous === previous.toUpperCase();
  return isUpperCase ? candidate.toUpperCase() : candidate;
}

export function isCssColor(value: string): boolean {
  return typeof CSS !== "undefined" && CSS.supports("color", value);
}
