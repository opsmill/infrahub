export function validateTextAttribute(
  {
    isRequired = false,
    minLength = 0,
    maxLength = 0,
  }: {
    isRequired?: boolean;
    minLength?: number | null;
    maxLength?: number | null;
  },
  value: string | null | undefined
): { success: true; data: string } | { success: false; error: string } {
  if (!value) {
    return isRequired ? { success: false, error: "Required" } : { success: true, data: "" };
  }

  if (minLength && minLength > 0 && value.length < minLength) {
    return {
      success: false,
      error: `Text must be at least ${minLength} characters long`,
    };
  }

  if (maxLength && maxLength > 0 && value.length > maxLength) {
    return {
      success: false,
      error: `Text must be at most ${maxLength} characters long`,
    };
  }

  return { success: true, data: value };
}
