import { FormFieldValue } from "@/components/form/type";

export const isRequired = ({ value }: FormFieldValue) => {
  return (value !== null && value !== undefined && value !== "") || "Required";
};
