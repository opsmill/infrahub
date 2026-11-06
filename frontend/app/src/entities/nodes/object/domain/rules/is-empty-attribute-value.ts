import * as R from "remeda";

/** `0` and `false` are values; an empty string, list or object is not. */
export function isEmptyAttributeValue(value: unknown): boolean {
  if (value === null || value === undefined || value === "") return true;
  if (Array.isArray(value)) return value.length === 0;
  if (R.isPlainObject(value)) return Object.keys(value).length === 0;
  return false;
}
