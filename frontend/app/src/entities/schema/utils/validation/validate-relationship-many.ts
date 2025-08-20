import type { FormRelationshipValue } from "@/shared/components/form/type";

export function validateRelationshipMany(
  params: { isRequired?: boolean; minCount?: number; maxCount?: number },
  value: FormRelationshipValue["value"]
): { success: true; data: FormRelationshipValue["value"] } | { success: false; error: string } {
  const { isRequired = false, minCount, maxCount } = params;

  if (value === null || value === undefined) {
    if (isRequired) {
      return { success: false, error: "Required" };
    } else {
      return { success: true, data: [] };
    }
  }

  if (!Array.isArray(value)) {
    return { success: false, error: "Value must be an array" };
  }

  if (minCount && value.length < minCount) {
    return { success: false, error: `Must select at least ${minCount} items` };
  }

  if (maxCount && value.length > maxCount) {
    return { success: false, error: `Cannot select more than ${maxCount} items` };
  }

  return { success: true, data: value };
}
