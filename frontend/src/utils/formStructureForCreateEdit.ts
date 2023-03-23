import {
  ControlType,
  DynamicFieldData
} from "../screens/edit-form-hook/dynamic-control-types";
import { iNodeSchema } from "../state/atoms/schema.atom";
import { iSchemaKindNameMap } from "../state/atoms/schemaKindName.atom";
import { iPeerDropdownOptions } from "./dropdownOptionsForRelatedPeers";

const getFormStructureForCreateEdit = (
  schema: iNodeSchema,
  dropdownOptions: iPeerDropdownOptions,
  schemaKindNameMap: iSchemaKindNameMap,
  row?: any
): DynamicFieldData[] => {
  if(!schema) {
    return [];
  }
  return [
    ...(schema.attributes || []).map((attribute) => ({
      fieldName: attribute.name,
      inputType: attribute.enum ? "select" : ("text" as ControlType),
      label: attribute.label ? attribute.label : attribute.name,
      options: attribute.enum?.map((row: any) => ({
        label: row,
        value: row,
      })),
      defaultValue: row && row[attribute.name] ? row[attribute.name].value : "",
      config: {
        required: attribute.optional === false ? "Required" : "",
      },
    })),
    ...(schema.relationships || [])
    .filter((relationship) => relationship.kind === "Attribute")
    .map((relationship) => ({
      fieldName: relationship.name,
      inputType:
          relationship.cardinality === "many"
            ? ("multiselect" as ControlType)
            : ("select" as ControlType),
      label: relationship.label ? relationship.label : relationship.name,
      options: dropdownOptions[schemaKindNameMap[relationship.peer]].map(
        (row: any) => ({
          label: row.display_label,
          value: row.id,
        })
      ),
      defaultValue: row
        ? relationship.cardinality === "many"
          ? row[relationship.name].map((item: any) => item.id)
          : row[relationship.name].id
        : "",
    })),
  ];
};

export default getFormStructureForCreateEdit;
