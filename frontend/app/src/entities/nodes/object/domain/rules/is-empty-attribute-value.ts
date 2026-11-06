import * as R from "remeda";

/** `0` and `false` are values, and so is an object holding `size: 0`, which `R.isEmptyish` misreads. */
export function isEmptyAttributeValue(value: unknown): boolean {
  if (value === null || value === undefined || value === "") return true;
  if (Array.isArray(value)) return value.length === 0;
  if (R.isPlainObject(value)) return Object.keys(value).length === 0;
  return false;
}
