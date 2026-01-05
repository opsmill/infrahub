import type { RegisterOptions } from "react-hook-form";

import type { SelectOption } from "@/shared/components/inputs/select-old";

import type { AttributeKind, AttributeSchema, RelationshipSchema } from "@/entities/schema/types";

import type { FormFieldError } from "./form";

// Interface for every field in a create/edit form
export interface DynamicFieldData {
  label: string;
  type: ControlType;
  name: string;
  peer?: string;
  kind?: AttributeKind;
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
  field?: AttributeSchema | RelationshipSchema;
}

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
