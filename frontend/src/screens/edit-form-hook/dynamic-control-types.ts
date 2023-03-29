import { RegisterOptions } from "react-hook-form";

export type ControlType = "text" | "select" | "multiselect" | "number" | "checkbox";
export type RelationshipCardinality = "one" | "many";

export interface SelectOption {
  label: string;
  value: string;
}

export interface DynamicFieldData {
  label: string;
  inputType: ControlType;
  fieldName: string;
  defaultValue: any;
  isAttribute: boolean;
  isRelationship: boolean;
  relationshipCardinality?: RelationshipCardinality;
  options: {
    values: SelectOption[];
  };
  config?: RegisterOptions;
}