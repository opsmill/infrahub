import { FormFieldValue, FormRelationshipValue } from "@/shared/components/form/type";

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

export const isMinCount = (minCount: number) => {
  return ({ value }: FormRelationshipValue) => {
    if (!value) return minCount === 0 || `Minimum ${minCount} required`;
    if (!Array.isArray(value)) return true;

    return value.length >= minCount || `Minimum ${minCount} required`;
  };
};

export const isMaxCount = (maxCount: number) => {
  return ({ value }: FormRelationshipValue) => {
    if (!value) return true;
    if (!Array.isArray(value)) return true;
    if (maxCount === 0) return true; // maxCount of 0 means no limit
    return value.length <= maxCount || `Maximum ${maxCount} allowed`;
  };
};
