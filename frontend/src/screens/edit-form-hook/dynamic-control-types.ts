import { RegisterOptions } from "react-hook-form";
import { SelectOption } from "../../components/inputs/select";
import { iPeerDropdownOptions } from "../../graphql/queries/objects/dropdownOptionsForRelatedPeers";
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
  options?: {
    values: SelectOption[];
  };
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
    case "Integer":
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

export const getInputTypeFromAttribute = (attribute: any) => {
  if (attribute.enum) {
    return "enum";
  }

  return getInputTypeFromKind(attribute.kind);
};

export const getInputTypeFromRelationship = (relationship: any, isInherited: boolean) => {
  if (relationship.cardinality === "many") {
    return "multiselect";
  }

  if (isInherited) {
    return "select2step";
  }

  return "select";
};

export const getOptionsFromAttribute = (attribute: any, value: any) => {
  if (attribute.kind === "List") {
    return value?.map((option: any) => ({
      name: option,
      id: option,
    }));
  }

  if (attribute.enum) {
    return attribute.enum?.map((option: any) => ({
      name: option,
      id: option,
    }));
  }

  if (attribute.choices) {
    return attribute.choices?.map((option: any) => ({
      ...option,
      id: option.name,
      name: option.label,
    }));
  }

  return [];
};

export const getOptionsFromRelationship = (
  dropdownOptions: iPeerDropdownOptions,
  relationship: any,
  isInherited: any,
  schemas: any,
  generics: any
) => {
  if (!isInherited && dropdownOptions[relationship.peer]) {
    return dropdownOptions[relationship.peer].map((row: any) => ({
      name: row.display_label,
      id: row.id,
    }));
  }

  const generic = generics.find((generic: any) => generic.kind === relationship.peer);

  if (generic) {
    return (generic.used_by || []).map((name: string) => {
      const relatedSchema = schemas.find((s: any) => s.kind === name);

      if (relatedSchema) {
        return {
          id: name,
          name: relatedSchema.name,
        };
      }
    });
  }

  return [];
};
