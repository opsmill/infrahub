import { isValid } from "date-fns";
import { SelectOption } from "../components/inputs/select";
import {
  DynamicFieldData,
  SchemaAttributeType,
  getInputTypeFromAttribute,
  getInputTypeFromRelationship,
} from "../screens/edit-form-hook/dynamic-control-types";
import { iGenericSchema, iNodeSchema } from "../state/atoms/schema.atom";
import { sortByOrderWeight } from "./common";
import {
  getFieldValue,
  getObjectRelationshipsForForm,
  getOptionsFromAttribute,
  getRelationshipOptions,
  getRelationshipValue,
  getSelectParent,
} from "./getSchemaObjectColumns";

const getIsDisabled = ({ owner, user, isProtected, isReadOnly }: any) => {
  // Field is read only
  if (isReadOnly) return true;

  // Field is available if there is no owner and if is_protected is not set to true
  if (!isProtected || !owner || user?.permissions?.isAdmin) return false;

  // Field is available only if is_protected is set to true and if the owner is the user
  return owner?.id !== user?.data?.sub;
};

const validate = (value: any, attribute: any = {}, optional?: boolean) => {
  const { default_value: defaultValue } = attribute;

  // If optionnal, no validator is needed (we try to validate if the value is defined or not)
  if (optional) {
    return true;
  }

  // If the attribute is of kind integer, then it should be a number
  if (attribute.kind === "Number" && Number.isInteger(value)) {
    return true;
  }

  // If the attribute is a date, check if the date is valid
  if (attribute.kind === "DateTime") {
    if (!value) {
      return "Required";
    }

    if (!isValid(value)) {
      return "Invalid date";
    }

    return true;
  }

  // The value is defined, then we can validate
  if (Array.isArray(value) ? value.length : value) {
    return true;
  }

  // If the value is false but itso is the default_value, then validate (checkbox example)
  if (defaultValue !== undefined && value === defaultValue) {
    return true;
  }

  // No value and the value is not the default_value, then mark as required
  return "Required";
};

const getFormStructureForCreateEdit = (
  schema: iNodeSchema | undefined,
  schemas: iNodeSchema[] | undefined,
  generics: iGenericSchema[],
  row?: any,
  user?: any,
  isUpdate?: boolean
): DynamicFieldData[] => {
  if (!schema) {
    return [];
  }

  const fieldsToParse = sortByOrderWeight([
    ...(schema.attributes ?? []),
    ...(getObjectRelationshipsForForm(schema) ?? []),
  ]);

  const fields = fieldsToParse
    .filter((field) => !field.read_only) // Ignore read only fields
    .map((field) => {
      // Parse a relationship
      if (field.cardinality) {
        const isInherited = !!generics.find((g) => g.kind === field.peer);

        return {
          name: field.name + (field.cardinality === "one" ? ".id" : ".list"),
          kind: "String" as SchemaAttributeType,
          peer: field.peer,
          type: getInputTypeFromRelationship(field, isInherited),
          label: field.label ? field.label : field.name,
          value: getRelationshipValue(row, field),
          options: getRelationshipOptions(row, field, schemas, generics),
          config: {
            validate: (value: any) => validate(value, undefined, field.optional),
          },
          isOptional: field.optional,
          isProtected: getIsDisabled({
            owner: row && row[field.name]?.properties?.owner,
            user,
            isProtected: row && row[field.name] && row[field.name]?.properties?.is_protected,
            isReadOnly: field.read_only,
          }),
          isInherited,
          parent: isInherited && getSelectParent(row, field), // Used by select 2 steps
          field,
          schema,
        };
      }

      // Parse an attribute
      const fieldValue = getFieldValue(row, field);

      // Quick fix to prevent password in update field,
      // TODO: remove HashedPassword test after new mutations are available to better handle accounts
      const isOptional = (field.optional || (isUpdate && field.kind === "HashedPassword")) ?? false;
      const isProtected = getIsDisabled({
        owner: row && row[field.name]?.owner,
        user,
        isProtected: row && row[field.name] && row[field.name].is_protected,
        isReadOnly: field.read_only,
      });

      return {
        name: field.name + ".value",
        kind: field.kind as SchemaAttributeType,
        type: getInputTypeFromAttribute(field),
        label: field.label || field.name,
        value: fieldValue,
        options: getOptionsFromAttribute(field, fieldValue),
        config: {
          validate: (value: any) => validate(value, field, isOptional),
        },
        isOptional,
        isReadOnly: field.read_only,
        isProtected,
        isUnique: field.unique,
        field,
        schema,
      };
    })
    .filter(Boolean);

  return fields;
};

export default getFormStructureForCreateEdit;

export const getFormStructureForMetaEdit = (
  row: any,
  type: "attribute" | "relationship",
  schemaList: iNodeSchema[]
): DynamicFieldData[] => {
  const sourceOwnerFields =
    type === "attribute" ? ["owner", "source"] : ["_relation__owner", "_relation__source"];

  const booleanFields =
    type === "attribute"
      ? ["is_visible", "is_protected"]
      : ["_relation__is_visible", "_relation__is_protected"];

  const relatedObjects: { [key: string]: string } = {
    source: "DataSource",
    owner: "DataOwner",
    _relation__source: "DataSource",
    _relation__owner: "DataOwner",
  };

  const sourceOwnerFormFields: DynamicFieldData[] = sourceOwnerFields.map((f) => {
    const schemaOptions: SelectOption[] = [
      ...schemaList
        .filter((schema) => {
          if ((schema.inherit_from || []).indexOf(relatedObjects[f]) > -1) {
            return true;
          } else {
            return false;
          }
        })
        .map((schema) => ({
          name: schema.kind,
          id: schema.name,
        })),
    ];

    return {
      name: f,
      kind: "Text",
      isAttribute: false,
      isRelationship: false,
      type: "select2step",
      label: f
        .split("_")
        .filter((r) => !!r)
        .join(" "),
      value: row?.[f],
      options: schemaOptions,
      config: {},
    };
  });

  const booleanFormFields: DynamicFieldData[] = booleanFields.map((f) => {
    return {
      name: f,
      kind: "Checkbox",
      isAttribute: false,
      isRelationship: false,
      type: "checkbox",
      label: f
        .split("_")
        .filter((r) => !!r)
        .join(" "),
      value: row?.[f],
      options: [],
      config: {},
    };
  });

  return [...sourceOwnerFormFields, ...booleanFormFields];
};

export const getFormStructureForMetaEditPaginated = (
  row: any,
  schemaList: iNodeSchema[]
): DynamicFieldData[] => {
  const sourceOwnerFields = ["owner", "source"];

  const booleanFields = ["is_visible", "is_protected"];

  const relatedObjects: { [key: string]: string } = {
    source: "LineageSource",
    owner: "LineageOwner",
    _relation__source: "LineageSource",
    _relation__owner: "LineageOwner",
  };

  const sourceOwnerFormFields: DynamicFieldData[] = sourceOwnerFields.map((field) => {
    const schemaOptions: SelectOption[] = [
      ...schemaList
        .filter((schema) => {
          if ((schema.inherit_from || []).indexOf(relatedObjects[field]) > -1) {
            return true;
          } else {
            return false;
          }
        })
        .map((schema) => ({
          name: schema.name,
          id: schema.kind,
        })),
    ];

    return {
      name: field,
      kind: "Text",
      isAttribute: false,
      isRelationship: false,
      type: "select2step",
      label: field.split("_").filter(Boolean).join(" "),
      value: row?.[field]?.id,
      options: schemaOptions,
      config: {},
      parent: row?.[field]?.__typename,
    };
  });

  const booleanFormFields: DynamicFieldData[] = booleanFields.map((field) => {
    return {
      name: field,
      kind: "Checkbox",
      isAttribute: false,
      isRelationship: false,
      type: "checkbox",
      label: field.split("_").filter(Boolean).join(" "),
      value: row?.[field],
      options: [],
      config: {},
    };
  });

  return [...sourceOwnerFormFields, ...booleanFormFields];
};
