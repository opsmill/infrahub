import { FormField } from "@/components/ui/form";
import { SchemaAttributeType } from "@/screens/edit-form-hook/dynamic-control-types";
import { ComponentProps } from "react";
import { SelectOption } from "@/components/inputs/select";
import { components } from "@/infraops";
import { IModelSchema } from "@/state/atoms/schema.atom";

type SourceType = "schema" | "user";

export type Source = {
  type: SourceType;
  label?: string | null;
  kind?: string;
  id?: string;
};

export type ProfileFieldValue = {
  source: {
    type: "profile";
    label: string | null;
    kind: string;
    id: string;
  };
  value: string | number | boolean | null;
};

export type FormAttributeValue =
  | {
      source: Source | null;
      value: string | number | boolean | null | undefined;
    }
  | ProfileFieldValue;

export type PoolFieldValue = {
  source: {
    type: "pool";
    label: string | null;
    kind: string;
    id: string;
  };
  value: { id: string } | { from_pool: { id: string } };
};

export type FormRelationshipValue =
  | {
      source: Source | null;
      value: { id: string } | Array<{ id: string }> | null | undefined;
    }
  | PoolFieldValue;

export type FormFieldValue = FormAttributeValue | FormRelationshipValue;

export type FormFieldProps = {
  defaultValue?: FormAttributeValue;
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
  field?:
    | components["schemas"]["AttributeSchema-Output"]
    | components["schemas"]["RelationshipSchema-Output"];
  schema?: IModelSchema;
};

export type DynamicEnumFieldProps = FormFieldProps & {
  type: "enum";
  items: Array<string>;
  field?:
    | components["schemas"]["AttributeSchema-Output"]
    | components["schemas"]["RelationshipSchema-Output"];
  schema?: IModelSchema;
};

export type DynamicRelationshipFieldProps = Omit<FormFieldProps, "defaultValue"> & {
  type: "relationship";
  defaultValue?: FormRelationshipValue;
  peer?: string;
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
