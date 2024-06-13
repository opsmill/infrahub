import { FormField } from "@/components/ui/form";
import { SchemaAttributeType } from "@/screens/edit-form-hook/dynamic-control-types";
import { ComponentProps } from "react";
import { SelectOption } from "@/components/inputs/select";
import { components } from "@/infraops";
import { IModelSchema } from "@/state/atoms/schema.atom";

export type FormFieldProps = {
  defaultValue?: string | number | boolean;
  description?: string;
  disabled?: boolean;
  label?: string;
  name: string;
  placeholder?: string;
  unique?: boolean;
  rules?: ComponentProps<typeof FormField>["rules"];
};

export type DynamicInputFieldProps = FormFieldProps & {
  type: Exclude<SchemaAttributeType, "Dropdown">;
};

export type DynamicDropdownFieldProps = FormFieldProps & {
  type: "Dropdown";
  items: Array<SelectOption>;
};

export type DynamicEnumFieldProps = FormFieldProps & {
  type: "enum";
  items: Array<string>;
};

export type DynamicRelationshipFieldProps = FormFieldProps & {
  type: "relationship";
  parent?: string;
  options?: SelectOption[];
  relationship: components["schemas"]["RelationshipSchema-Output"];
  schema: IModelSchema;
};

export type DynamicFieldProps =
  | DynamicInputFieldProps
  | DynamicDropdownFieldProps
  | DynamicEnumFieldProps
  | DynamicRelationshipFieldProps;
