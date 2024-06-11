import { FormField } from "@/components/ui/form";
import { SchemaAttributeType } from "@/screens/edit-form-hook/dynamic-control-types";
import { ComponentProps } from "react";

export type FormFieldProps = {
  defaultValue?: string | number | boolean;
  label: string;
  name: string;
  placeholder?: string;
  rules?: ComponentProps<typeof FormField>["rules"];
};

export interface DynamicFieldProps extends FormFieldProps {
  type: SchemaAttributeType;
}
