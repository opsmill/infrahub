import { RegisterOptions } from "react-hook-form";
import { SelectOption } from "../../components/inputs/select";
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
}

// Different values for "kind" property of each attribute in the schema
export type SchemaAttributeType =
  | "ID"
  | "Text"
  | "Number"
  | "TextArea"
  | "DateTime"
  | "Email"
  | "Password"
  | "HashedPassword"
  | "Hierarchy"
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
  | "Boolean"
  | "JSON"
  | "Dropdown";

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

export type RelationshipCardinality = "one" | "many";

export const getInputTypeFromKind = (kind: SchemaAttributeType): ControlType => {
  switch (kind) {
    case "List":
      return "list";
    case "Dropdown":
      return "dropdown";
    case "TextArea":
      return "textarea";
    case "Number":
    case "Bandwidth":
      return "number";
    case "Checkbox":
    case "Boolean":
      return "checkbox";
    case "DateTime":
      return "datepicker";
    case "JSON":
      return "json";
    case "Password":
    case "HashedPassword":
      return "password";
    case "Text":
    case "ID":
    case "Email":
    case "URL":
    case "File":
    case "MacAddress":
    case "Color":
    case "IPHost":
    case "IPNetwork":
    case "Any":
    case "String":
    default:
      return "text";
  }
};

export const getInputTypeFromAttribute = (attribute: any): ControlType => {
  if (attribute.enum) {
    return "enum";
  }

  return getInputTypeFromKind(attribute.kind);
};

export const getInputTypeFromRelationship = (
  relationship: any,
  isInherited: boolean
): ControlType => {
  if (relationship.cardinality === "many") {
    return "multiselect";
  }

  if (isInherited) {
    return "select2step";
  }

  return "select";
};
