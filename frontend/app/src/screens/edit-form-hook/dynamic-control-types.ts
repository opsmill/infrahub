import { SelectOption } from "@/components/inputs/select";
import { SCHEMA_ATTRIBUTE_KIND } from "@/config/constants";
import { components } from "@/infraops";
import { RegisterOptions } from "react-hook-form";
import { FormFieldError } from "./form";

// Interface for every field in a create/edit form
export interface DynamicFieldData {
  label: string;
  type: ControlType;
  name: string;
  peer?: string;
  kind?: SchemaAttributeType;
  placeholder?: string;
  value: any;
  options?: SelectOption[];
  config?: RegisterOptions;
  error?: FormFieldError;
  isProtected?: boolean;
  isOptional?: boolean;
  isReadOnly?: boolean;
  isUnique?: boolean;
  disabled?: boolean;
  preventObjectsCreation?: boolean;
  parent?: string;
  field?:
    | components["schemas"]["AttributeSchema-Output"]
    | components["schemas"]["RelationshipSchema-Output"];
}

// Different values for "kind" property of each attribute in the schema
export type SchemaAttributeType =
  (typeof SCHEMA_ATTRIBUTE_KIND)[keyof typeof SCHEMA_ATTRIBUTE_KIND];

// Different kind of form inputs
export type ControlType =
  | "text"
  | "password"
  | "textarea"
  | "select"
  | "select2step"
  | "multiselect"
  | "list"
  | "number"
  | "checkbox"
  | "switch"
  | "datepicker"
  | "json"
  | "dropdown"
  | "enum"
  | "color";
