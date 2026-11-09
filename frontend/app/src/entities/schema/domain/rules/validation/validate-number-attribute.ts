export function validateNumberAttribute(
  params: { isRequired?: boolean; min?: number | null; max?: number | null },
  value: number | null | undefined
): { success: true; data: number } | { success: false; error: string } {
  const { isRequired = false, min, max } = params;

  if (value === null || value === undefined) {
    if (isRequired) {
      return { success: false, error: "Required" };
    } else {
      return { success: true, data: 0 };
    }
  }

  if (isNaN(value)) {
    return { success: false, error: "Value must be a number" };
  }

  if (min && value < min) {
    return { success: false, error: `Value must be at least ${min}` };
  }

  if (max && value > max) {
    return { success: false, error: `Value must be at most ${max}` };
  }

  return { success: true, data: value };
}
