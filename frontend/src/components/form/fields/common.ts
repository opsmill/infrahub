import { ComponentProps } from "react";
import { SchemaAttributeType } from "../../../screens/edit-form-hook/dynamic-control-types";
import { FormField } from "../@/ui/form";

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
