import type { FormFieldValue } from "@/shared/components/form/type";

export const isRequired = ({ value }: Pick<FormFieldValue, "value">) => {
  return (value !== null && value !== undefined && value !== "") || "Required";
};

export const isMinLength =
  (minLength: number) =>
  ({ value }: Pick<FormFieldValue, "value">) => {
    if (!value) return "Required";
    if (typeof value !== "string") return true;

    return value.length >= minLength || `Value must be at least ${minLength} characters long`;
  };
