import { FormFieldValue } from "@/components/form/type";

export const isRequired = ({ value }: FormFieldValue) => {
  return (value !== null && value !== undefined && value !== "") || "Required";
};

export const isMinLength =
  (minLength: number) =>
  ({ value }: FormFieldValue) => {
    if (!value) return "Required";
    if (typeof value !== "string") return true;

    return value.length >= minLength || `Name must be at least ${minLength} characters long`;
  };
