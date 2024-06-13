import { FormField } from "@/components/ui/form";
import { SchemaAttributeType } from "@/screens/edit-form-hook/dynamic-control-types";
import { ComponentProps } from "react";
import { SelectOption } from "@/components/inputs/select";
import { components } from "@/infraops";
import { IModelSchema } from "@/state/atoms/schema.atom";

export type FormFieldProps = {
  defaultValue?: string | number | boolean;
  label?: string;
  name: string;
  placeholder?: string;
  rules?: ComponentProps<typeof FormField>["rules"];
};

type DynamicInputFieldProps = FormFieldProps & {
  type: Exclude<SchemaAttributeType, "Dropdown">;
};

type DynamicDropdownFieldProps = FormFieldProps & {
  type: "Dropdown";
  items: Array<SelectOption>;
};

export type DynamicRelationshipFieldProps = FormFieldProps & {
  type: "relationship";
  parent?: string;
  relationship: components["schemas"]["RelationshipSchema-Output"];
  schema: IModelSchema;
};

export type DynamicFieldProps =
  | DynamicInputFieldProps
  | DynamicDropdownFieldProps
  | DynamicRelationshipFieldProps;
