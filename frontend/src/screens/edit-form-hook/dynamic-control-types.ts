import { RegisterOptions } from "react-hook-form";
import { SelectOption } from "../../components/select";
import { FormFieldError } from "./form";

// Different values for "kind" property of each attribute in the schema
export type SchemaAttributeType =
  | "ID"
  | "Text"
  | "Number"
  | "TextArea"
  | "DateTime"
  | "Email"
  | "Password"
  | "URL"
  | "File"
  | "MacAddress"
  | "Color"
  | "Bandwidth"
  | "IPHost"
  | "IPNetwork"
  | "Checkbox"
  | "List"
  | "Any"
  | "String"
  | "Integer"
  | "Boolean"
  | "JSON";

// Different kind of form inputs
export type ControlType =
  | "text"
  | "password"
  | "textarea"
  | "select"
  | "select2step"
  | "multiselect"
  | "number"
  | "checkbox"
  | "switch"
  | "datepicker"
  | "json";

export type RelationshipCardinality = "one" | "many";

export const getFormInputControlTypeFromSchemaAttributeKind = (
  kind: SchemaAttributeType
): ControlType => {
  switch (kind) {
    case "Text":
    case "ID":
    case "Email":
    case "Password":
    case "URL":
    case "File":
    case "MacAddress":
    case "Color":
    case "IPHost":
    case "IPNetwork":
    case "List":
    case "Any":
    case "String":
      return "text";
    case "TextArea":
      return "textarea";
    case "Number":
    case "Bandwidth":
    case "Integer":
      return "number";
    case "Checkbox":
    case "Boolean":
      return "checkbox";
    case "DateTime":
      return "datepicker";
    case "JSON":
      return "json";
    default:
      return "text";
  }
};

// Interface for every field in a create/edit form
export interface DynamicFieldData {
  label: string;
  type: ControlType;
  name: string;
  kind?: SchemaAttributeType;
  value: any;
  options?: {
    values: SelectOption[];
  };
  config?: RegisterOptions;
  error?: FormFieldError;
  isProtected?: boolean;
  isOptionnal?: boolean;
  disabled?: boolean;
}
