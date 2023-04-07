import {
  ControlType,
  DynamicFieldData,
  getFormInputControlTypeFromSchemaAttributeKind,
  RelationshipCardinality,
  SchemaAttributeType,
  SelectOption
} from "../screens/edit-form-hook/dynamic-control-types";
import { iGenericSchemaMapping, iNodeSchema } from "../state/atoms/schema.atom";
import { iSchemaKindNameMap } from "../state/atoms/schemaKindName.atom";
import { iPeerDropdownOptions } from "./dropdownOptionsForRelatedPeers";

const getFormStructureForCreateEdit = (
  schema: iNodeSchema,
  dropdownOptions: iPeerDropdownOptions,
  schemaKindNameMap: iSchemaKindNameMap,
  genericSchemaMap: iGenericSchemaMapping,
  row?: any
): DynamicFieldData[] => {
  if (!schema) {
    return [];
  }

  const formFields: DynamicFieldData[] = [];

  schema.attributes?.forEach((attribute) => {
    let options: SelectOption[] = [];
    if (attribute.enum) {
      options = attribute.enum?.map((row: any) => ({
        label: row,
        value: row,
      }));
    }

    formFields.push({
      fieldName: attribute.name,
      type: attribute.kind as SchemaAttributeType,
      isAttribute: true,
      isRelationship: false,
      inputType: attribute.enum ? "select" : getFormInputControlTypeFromSchemaAttributeKind(attribute.kind as SchemaAttributeType),
      label: attribute.label ? attribute.label : attribute.name,
      defaultValue: row && row[attribute.name] ? row[attribute.name] : "",
      options: {
        values: options,
      },
      config: {
        required: attribute.optional === false ? "Required" : "",
      },
    });
  });

  schema.relationships
  ?.filter((relationship) => relationship.kind === "Attribute")
  .forEach((relationship) => {
    let options: SelectOption[] = [];
    if (dropdownOptions[schemaKindNameMap[relationship.peer]]) {
      options = dropdownOptions[schemaKindNameMap[relationship.peer]].map(
        (row: any) => ({
          label: row.display_label,
          value: row.id,
        })
      );
    }
    formFields.push({
      fieldName: relationship.name,
      type: "String",
      isAttribute: false,
      isRelationship: true,
      relationshipCardinality: relationship.cardinality as RelationshipCardinality,
      inputType:
          relationship.cardinality === "many"
            ? ("multiselect" as ControlType)
            : ("select" as ControlType),
      label: relationship.label ? relationship.label : relationship.name,
      defaultValue: row ? row[relationship.name] : "",
      options: {
        values: options,
      },
    });
  });

  return formFields;
};

export default getFormStructureForCreateEdit;
