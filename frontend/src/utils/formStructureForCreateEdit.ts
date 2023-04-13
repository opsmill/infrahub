import { HasNameAndID } from "../components-form/select";
import {
  ControlType,
  DynamicFieldData,
  getFormInputControlTypeFromSchemaAttributeKind,
  SchemaAttributeType
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
    let options: HasNameAndID[] = [];
    if (attribute.enum) {
      options = attribute.enum?.map((row: any) => ({
        name: row,
        id: row,
      }));
    }

    formFields.push({
      name: attribute.name + ".value",
      kind: attribute.kind as SchemaAttributeType,
      type: attribute.enum ? "select" : getFormInputControlTypeFromSchemaAttributeKind(attribute.kind as SchemaAttributeType),
      label: attribute.label ? attribute.label : attribute.name,
      value: row && row[attribute.name] ? row[attribute.name].value : "",
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
    let options: HasNameAndID[] = [];
    if (dropdownOptions[schemaKindNameMap[relationship.peer]]) {
      options = dropdownOptions[schemaKindNameMap[relationship.peer]].map(
        (row: any) => ({
          name: row.display_label,
          id: row.id,
        })
      );
    }
    formFields.push({
      name: relationship.name + (relationship.cardinality === "one" ? ".id" : ".list"),
      kind: "String",
      type:
          relationship.cardinality === "many"
            ? ("multiselect" as ControlType)
            : ("select" as ControlType),
      label: relationship.label ? relationship.label : relationship.name,
      value: row && row[relationship.name] ? relationship.cardinality === "one" ? row[relationship.name].id : row[relationship.name].map((item: any) => item.id) : "",
      options: {
        values: options,
      },
    });
  });

  return formFields;
};

export default getFormStructureForCreateEdit;

export const getFormStructureForMetaEdit = (
  row: any,
  type: "attribute" | "relationship",
  attributeOrRelationshipName: any,
  schemaList: iNodeSchema[],
): DynamicFieldData[] => {
  const sourceOwnerFields = type === "attribute" ? ["owner", "source"] : ["_relation__owner", "_relation__source"];
  const booleanFields = type === "attribute" ? ["is_visible", "is_protected"] : ["_relation__is_visible", "_relation__is_protected"];

  const relatedObjects: { [key: string]: string; } = {
    "source": "DataSource",
    "owner": "DataOwner",
    "_relation__source": "DataSource",
    "_relation__owner": "DataOwner",
  };


  const sourceOwnerFormFields: DynamicFieldData[] = sourceOwnerFields.map(f => {
    const metaFieldName = attributeOrRelationshipName + "." + f;
    const schemaOptions: HasNameAndID[] = [
    //   {
    //   name: "",
    //   id: "",
    // },
      ...schemaList.filter(schema => {
        if((schema.inherit_from || []).indexOf(relatedObjects[f]) > -1) {
          return true;
        } else {
          return false;
        }
      }).map(schema => ({
        name: schema.kind,
        id: schema.name,
      }))];

    return {
      name: metaFieldName,
      kind: "Text",
      isAttribute: false,
      isRelationship: false,
      type: "select2step",
      label: f.split("_").filter(r => !!r).join(" "),
      value: row?.[attributeOrRelationshipName]?.[f],
      options: {
        values: schemaOptions,
      },
      config: {},
    };
  });

  const booleanFormFields: DynamicFieldData[] = booleanFields.map(f => {
    const metaFieldName = attributeOrRelationshipName + "." + f;
    return {
      name: metaFieldName,
      kind: "Checkbox",
      isAttribute: false,
      isRelationship: false,
      type: "checkbox",
      label: f.split("_").filter(r => !!r).join(" "),
      value: row?.[attributeOrRelationshipName]?.[f],
      options: {
        values: [],
      },
      config: {},
    };
  });

  return [...sourceOwnerFormFields, ...booleanFormFields];
};
