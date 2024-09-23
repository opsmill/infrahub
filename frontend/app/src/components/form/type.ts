import { FormField } from "@/components/ui/form";
import { SchemaAttributeType } from "@/screens/edit-form-hook/dynamic-control-types";
import { ComponentProps } from "react";
import { SelectOption } from "@/components/inputs/select";
import { IModelSchema } from "@/state/atoms/schema.atom";
import { DropdownOption } from "@/components/inputs/dropdown";
import { AttributeSchema, RelationshipSchema } from "@/screens/schema/types";
import { Node } from "@/utils/getObjectItemDisplayValue";

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

export type PoolSource = {
  type: "pool";
  label: string | null;
  kind: string;
  id: string;
};

export type AttributeValueFormPool = {
  source: PoolSource;
  value: { from_pool: { id: string } };
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
  | EmptyFieldValue
  | AttributeValueFormPool;

export type RelationshipOneValueFromUser = {
  source: {
    type: SourceType;
  };
  value: Node | null;
};

export type RelationshipManyValueFromUser = {
  source: {
    type: SourceType;
  };
  value: Array<Node> | null;
};

export type RelationshipValueFromPool = {
  source: PoolSource;
  value: { from_pool: { id: string } } | Node;
};

export type RelationshipValueFromUser =
  | RelationshipOneValueFromUser
  | RelationshipManyValueFromUser;

export type FormRelationshipValue =
  | RelationshipValueFromUser
  | RelationshipValueFromPool
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
  onChange?: (value: FormFieldValue) => void;
};

export type DynamicInputFieldProps = FormFieldProps & {
  type: Exclude<SchemaAttributeType, "Dropdown">;
};

export type DynamicNumberFieldProps = FormFieldProps & {
  type: "Number";
  pools?: Array<NumberPoolData>;
};

export type DynamicDropdownFieldProps = FormFieldProps & {
  type: "Dropdown";
  items: Array<DropdownOption>;
  field?: AttributeSchema;
  schema?: IModelSchema;
};

export type DynamicEnumFieldProps = FormFieldProps & {
  type: "enum";
  items: Array<unknown>;
  field?: AttributeSchema;
  schema?: IModelSchema;
};

export type DynamicRelationshipFieldProps = Omit<FormFieldProps, "defaultValue"> & {
  type: "relationship";
  defaultValue?: FormRelationshipValue;
  peer?: string;
  parent?: string;
  options?: SelectOption[];
  relationship: RelationshipSchema;
  schema: IModelSchema;
};

export type DynamicRelationshipManyFieldProps = Omit<FormFieldProps, "defaultValue"> & {
  type: "relationship";
  defaultValue?: RelationshipManyValueFromUser;
  peer?: string;
  parent?: string;
  options?: SelectOption[];
  relationship: RelationshipSchema;
  schema: IModelSchema;
};

export type DynamicFieldProps =
  | DynamicInputFieldProps
  | DynamicNumberFieldProps
  | DynamicDropdownFieldProps
  | DynamicEnumFieldProps
  | DynamicRelationshipFieldProps;

export const isFormFieldValueFromPool = (
  fieldData: FormFieldValue
): fieldData is RelationshipValueFromPool => fieldData.source?.type === "pool";

export type NumberPoolData = {
  id: string;
  label: string;
  kind: string;
  nodeAttribute: {
    id: string;
    name: string;
  };
};
