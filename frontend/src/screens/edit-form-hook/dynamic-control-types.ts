import { RegisterOptions } from "react-hook-form";
import { HasNameAndID } from "../../components-form/select";

// Different values for "kind" property of each attribute in the schema
export type SchemaAttributeType = "ID" | "Text" | "Number" | "TextArea" | "DateTime" | "Email" | "Password" | "URL" | "File" | "MacAddress" | "Color" | "Bandwidth" | "IPHost" | "IPNetwork" | "Checkbox" | "List" | "Any" | "String" | "Integer" | "Boolean";

// Different kind of form inputs
export type ControlType = "text" | "select" | "select2step" | "multiselect" | "number" | "checkbox";

export type RelationshipCardinality = "one" | "many";

export const getFormInputControlTypeFromSchemaAttributeKind = (kind: SchemaAttributeType): ControlType => {
  switch(kind) {
    case "Text":
    case "TextArea":
    case "ID":
    case "DateTime":
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

    case "Number":
    case "Bandwidth":
    case "Integer":
      return "number";

    case "Checkbox":
    case "Boolean":
      return "checkbox";

    default:
      return "text";
  }
};

export interface SelectOption {
  label: string;
  value: string;
}

// Interface for every field in a create/edit form
export interface DynamicFieldData {
  label: string;
  type: ControlType;
  name: string;
  kind: SchemaAttributeType;
  value: any;
  options: {
    values: HasNameAndID[];
  };
  config?: RegisterOptions;
}