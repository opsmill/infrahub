import { RegisterOptions } from "react-hook-form";

// Different values for "kind" property of each attribute in the schema
export type SchemaAttributeType = "ID" | "Text" | "Number" | "TextArea" | "DateTime" | "Email" | "Password" | "URL" | "File" | "MacAddress" | "Color" | "Bandwidth" | "IPHost" | "IPNetwork" | "Checkbox" | "List" | "Any" | "String" | "Integer" | "Boolean";

// Different values for the type of "Form input types" when in the create/edit forms
export type ControlType = "text" | "select" | "multiselect" | "number" | "checkbox";

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

export interface DynamicFieldData {
  label: string;
  inputType: ControlType;
  fieldName: string;
  type: SchemaAttributeType;
  defaultValue: any;
  isAttribute: boolean;
  isRelationship: boolean;
  relationshipCardinality?: RelationshipCardinality;
  options: {
    values: SelectOption[];
  };
  config?: RegisterOptions;
}