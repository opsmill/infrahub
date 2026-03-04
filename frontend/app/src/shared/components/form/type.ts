import type { ComponentProps } from "react";

import type { DropdownOption } from "@/shared/components/inputs/dropdown";
import type { SelectOption } from "@/shared/components/inputs/select-old";
import type { FormField } from "@/shared/components/ui/form";

import type { NodeCore } from "@/entities/nodes/types";
import type { NumberPool } from "@/entities/resource-manager/domain/type";
import type {
  AttributeKind,
  AttributeSchema,
  ModelSchema,
  RelationshipSchema,
} from "@/entities/schema/types";

type SourceType = "schema" | "user";

export type EmptyFieldValue = {
  source: null;
  value: null;
};

export type PoolSource = {
  type: "pool";
  label: string | null;
  kind: string;
  id: string;
  fromTemplate?: boolean;
};

export type ProfileSource = {
  type: "profile";
  label: string | null;
  kind: string;
  id: string;
};

export type TemplateSource = {
  type: "template";
  label: string | null;
  kind: string;
  id: string;
};

export type AttributeValueFromProfile = {
  source: ProfileSource;
  value: string | number | boolean | null;
};

export type AttributeValueFromPool = {
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
      value: string | string[] | number | boolean | null;
    }
  | AttributeValueForCheckbox;

export type AttributeValueFromTemplate = {
  source: TemplateSource;
  value: string | string[] | number | boolean | null;
};

export type FormAttributeValue =
  | AttributeValueFromUser
  | AttributeValueFromProfile
  | AttributeValueFromPool
  | AttributeValueFromTemplate
  | EmptyFieldValue;

export type RelationshipOneValueFromUser = {
  source: {
    type: SourceType;
  };
  value: NodeCore | null;
};

export type RelationshipManyValueFromUser = {
  source: {
    type: SourceType;
  };
  value: Array<NodeCore> | null;
};

export type RelationshipOneValueFromTemplate = {
  source: TemplateSource;
  value: NodeCore | null;
};

export type RelationshipManyValueFromTemplate = {
  source: TemplateSource;
  value: Array<NodeCore> | null;
};

export type RelationshipValueFromPool = {
  source: PoolSource;
  value: NodeCore | { from_pool: { id: string } };
};

export type RelationshipOneValueFromProfile = {
  source: ProfileSource;
  value: NodeCore | null;
};

export type RelationshipManyValueFromProfile = {
  source: ProfileSource;
  value: Array<NodeCore> | null;
};

export type RelationshipValueFromUser =
  | RelationshipOneValueFromUser
  | RelationshipManyValueFromUser;

export type RelationshipValueFromTemplate =
  | RelationshipOneValueFromTemplate
  | RelationshipManyValueFromTemplate;

export type RelationshipValueFromProfile =
  | RelationshipOneValueFromProfile
  | RelationshipManyValueFromProfile;

export type FormRelationshipValue =
  | RelationshipValueFromUser
  | RelationshipValueFromPool
  | RelationshipValueFromTemplate
  | RelationshipValueFromProfile
  | EmptyFieldValue;

export type FormFieldValue = FormAttributeValue | FormRelationshipValue;

export type FormFieldProps = {
  attribute: AttributeSchema;
  defaultValue?: FormAttributeValue;
  description?: string;
  disabled?: boolean;
  label?: string;
  name: string;
  placeholder?: string;
  unique?: boolean;
  rules?: ComponentProps<typeof FormField>["rules"];
  onChange?: (value: FormFieldValue) => void;
  // Indicates the form is used for bulk updates, enabling explicit null-setting UI
  isBulkUpdate?: boolean;
  pool?: {
    kind: string;
    defaultAllocatedObjectKind: string;
    fromPoolRelationshipName?: string;
  };
  shouldUnregister?: boolean;
};

export type DynamicInputFieldProps = FormFieldProps & {
  type: Exclude<AttributeKind, "Dropdown">;
};

export type DynamicNumberFieldProps = FormFieldProps & {
  type: "Number";
  pools?: Array<NumberPool>;
};

export type DynamicDropdownFieldProps = FormFieldProps & {
  type: "Dropdown";
  items: Array<DropdownOption>;
  schema?: ModelSchema;
};

export type DynamicEnumFieldProps = FormFieldProps & {
  type: "enum";
  items: Array<unknown>;
  schema?: ModelSchema;
};

export type DynamicSelectFieldProps = FormFieldProps & {
  type: "select";
  items: Array<{ key: string; label: string }>;
};

export type DynamicKindFieldProps = FormFieldProps & {
  type: "kind";
};

export type DynamicAttributeFieldProps =
  | DynamicInputFieldProps
  | DynamicNumberFieldProps
  | DynamicDropdownFieldProps
  | DynamicEnumFieldProps
  | DynamicSelectFieldProps
  | DynamicKindFieldProps;

export type RelationshipFieldType = "relationship" | "relationship-add" | "relationship-remove";

export interface DynamicRelationshipFieldProps
  extends Omit<FormFieldProps, "defaultValue" | "attribute"> {
  type: RelationshipFieldType;
  defaultValue?: FormRelationshipValue;
  relationship: RelationshipSchema;
  peer?: string;
  parent?: string;
  options?: SelectOption[];
  peerField?: string;
}

export type DynamicFieldProps = DynamicAttributeFieldProps | DynamicRelationshipFieldProps;

export const isFormFieldValueFromPool = (
  fieldData: FormFieldValue
): fieldData is RelationshipValueFromPool => fieldData.source?.type === "pool";

export const isFormFieldValueFromTemplate = (
  fieldData: FormFieldValue
): fieldData is AttributeValueFromTemplate => fieldData.source?.type === "template";
