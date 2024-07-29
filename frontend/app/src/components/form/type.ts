import { FormField } from "@/components/ui/form";
import { SchemaAttributeType } from "@/screens/edit-form-hook/dynamic-control-types";
import { ComponentProps } from "react";
import { SelectOption } from "@/components/inputs/select";
import { components } from "@/infraops";
import { IModelSchema } from "@/state/atoms/schema.atom";

type SourceType = "schema" | "user";

export type EmptyFieldValue = {
  source: null;
  value: null;
};

export type AttributeValueFromProfile = {
  source: {
    type: "profile";
    label: string | null;
    kind: string;
    id: string;
  };
  value: string | number | boolean | null;
};

export type AttributeValueForCheckbox = {
  source: null;
  value: boolean;
};

export type AttributeValueFromUser =
  | {
      source: {
        type: SourceType;
      };
      value: string | number | boolean | null;
    }
  | AttributeValueForCheckbox;

export type FormAttributeValue =
  | AttributeValueFromUser
  | AttributeValueFromProfile
  | EmptyFieldValue;

export type RelationshipValueFormPool = {
  source: {
    type: "pool";
    label: string | null;
    kind: string;
    id: string;
  };
  value: { id: string } | { from_pool: { id: string } };
};

export type RelationshipValueFormUser = {
  source: {
    type: SourceType;
  };
  value: { id: string } | Array<{ id: string }> | null;
};

export type FormRelationshipValue =
  | RelationshipValueFormUser
  | RelationshipValueFormPool
  | EmptyFieldValue;

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

export const isFormFieldValueFromPool = (
  fieldData: FormFieldValue
): fieldData is RelationshipValueFormPool => fieldData.source?.type === "pool";
