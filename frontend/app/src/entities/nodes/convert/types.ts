import type { EmptyFieldValue, FormFieldValue } from "@/shared/components/form/type";

import type { NodeCore, NodeObject } from "@/entities/nodes/types";
import type { ModelSchema } from "@/entities/schema/types";

export interface ConvertFieldMapping {
  is_mandatory: boolean;
  source_field_name: string | null;
  relationship_cardinality: string | null;
}

export type ConvertSource = {
  type: "source";
  name: string;
};

export type ConvertFormFieldValue =
  | {
      source: ConvertSource;
      value: FormFieldValue["value"];
    }
  | EmptyFieldValue;

export interface ConvertSourceInputProps {
  sourceObject: NodeObject;
  sourceSchema: ModelSchema;
  mapping?: ConvertFieldMapping;
  className?: string;
  value: ConvertFormFieldValue;
  onChange: (value: ConvertFormFieldValue) => void;
}

export interface ConvertSourceRelationshipInputProps extends ConvertSourceInputProps {
  peer: string;
}

export interface ConvertSourceOption {
  source: {
    type: "source";
    name: string;
    label: string | null | undefined;
  };
  isDefaultMatch: boolean;
}

export interface AttributeSourceOption extends ConvertSourceOption {
  value: string | string[] | number | boolean | null;
  label: React.ReactNode;
}

export interface RelationshipOneSourceOption extends ConvertSourceOption {
  value: NodeCore | null;
}

export interface RelationshipManySourceOption extends ConvertSourceOption {
  value: Array<NodeCore> | null;
}
