import type { DynamicFieldProps } from "@/shared/components/form/type";

// Keeps only the fields named in the allowlist, in allowlist order.
export const pickAllowlistedFields = (
  fields: Array<DynamicFieldProps>,
  allowlist: Array<string>
): Array<DynamicFieldProps> =>
  allowlist.flatMap((name) => fields.find((field) => field.name === name) ?? []);
