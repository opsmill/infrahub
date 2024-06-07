import { ComponentProps } from "react";
import { FormField } from "../../ui/form";
import { SchemaAttributeType } from "../../../screens/edit-form-hook/dynamic-control-types";

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
