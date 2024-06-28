import { DynamicFieldProps } from "./type";
import { genericsState, iGenericSchema, iNodeSchema, schemaState } from "@/state/atoms/schema.atom";
import { SchemaAttributeType } from "@/screens/edit-form-hook/dynamic-control-types";
import { sortByOrderWeight } from "@/utils/common";
import { SCHEMA_ATTRIBUTE_KIND } from "@/config/constants";
import {
  getObjectRelationshipsForForm,
  getOptionsFromAttribute,
  getRelationshipOptions,
  getRelationshipValue,
  getSelectParent,
} from "@/utils/getSchemaObjectColumns";
import { AttributeType } from "@/utils/getObjectItemDisplayValue";
import { store } from "@/state";
import { getIsDisabled } from "@/utils/formStructureForCreateEdit";
import { components } from "@/infraops";

type GetFormFieldsFromSchema = {
  schema: iNodeSchema | iGenericSchema;
  profile?: Object;
  initialObject?: Record<string, AttributeType>;
  user?: any;
  isFilterForm?: boolean;
};

export const getFormFieldsFromSchema = ({
  schema,
  profile,
  initialObject,
  user,
  isFilterForm,
}: GetFormFieldsFromSchema): Array<DynamicFieldProps> => {
  const unorderedFields = [
    ...(schema.attributes ?? []),
    ...getObjectRelationshipsForForm(schema),
  ].filter((attribute) => !attribute.read_only);
  const orderedFields: typeof unorderedFields = sortByOrderWeight(unorderedFields);

  const formFields = orderedFields.map((attribute) => {
    const disabled = getIsDisabled({
      owner: initialObject && initialObject[attribute.name]?.owner,
      user,
      isProtected:
        initialObject &&
        initialObject[attribute.name] &&
        initialObject[attribute.name].is_protected,
      isReadOnly: attribute.read_only,
    });

    const basicFomFieldProps = {
      name: attribute.name,
      label: attribute.label ?? undefined,
      defaultValue: isFilterForm
        ? null
        : getObjectDefaultValue({ fieldSchema: attribute, initialObject, profile }),
      description: attribute.description ?? undefined,
      disabled,
      type: attribute.kind as Exclude<SchemaAttributeType, "Dropdown">,
      rules: {
        required: !isFilterForm && !attribute.optional,
      },
    };

    if ("peer" in attribute) {
      const nodes = store.get(schemaState);
      const generics = store.get(genericsState);

      return {
        ...basicFomFieldProps,
        type: "relationship",
        defaultValue: getRelationshipValue({ field: attribute, row: initialObject }),
        parent: getSelectParent(initialObject, attribute),
        options: getRelationshipOptions(initialObject, attribute, nodes, generics),
        relationship: attribute,
        schema,
      };
    }

    if (attribute.kind === SCHEMA_ATTRIBUTE_KIND.DROPDOWN) {
      return {
        ...basicFomFieldProps,
        type: SCHEMA_ATTRIBUTE_KIND.DROPDOWN,
        unique: attribute.unique,
        field: attribute,
        schema: schema,
        items: (attribute.choices ?? []).map((choice) => ({
          id: choice.id ?? choice.name,
          name: choice.label ?? choice.name,
          color: choice.color ?? undefined,
          description: choice.description ?? undefined,
        })),
      };
    }

    if (attribute.kind === SCHEMA_ATTRIBUTE_KIND.TEXT && Array.isArray(attribute.enum)) {
      return {
        ...basicFomFieldProps,
        type: "enum",
        field: attribute,
        schema: schema,
        unique: attribute.unique,
        items: getOptionsFromAttribute(attribute, basicFomFieldProps.defaultValue),
      };
    }

    return {
      ...basicFomFieldProps,
      unique: attribute.unique,
    };
  });

  // Allow kind filter for generic
  if (isFilterForm && schema.used_by?.length) {
    return [
      {
        name: "kind",
        label: "Kind",
        description: "Select a kind to filter nodes",
        type: "Dropdown",
        items: schema.used_by.map((kind) => ({
          id: kind,
          name: kind,
        })),
      },
      ...formFields,
    ];
  }

  return formFields;
};

export type GetObjectDefaultValue = {
  fieldSchema: GetObjectDefaultValueFromSchema;
  initialObject?: Record<string, AttributeType>;
  profile?: Record<string, AttributeType>;
};

export const getObjectDefaultValue = ({
  fieldSchema,
  initialObject,
  profile,
}: GetObjectDefaultValue) => {
  const currentFieldValue = initialObject?.[fieldSchema.name]?.value;
  const defaultValueFromProfile = profile?.[fieldSchema.name]?.value;
  const defaultValueFromSchema = getDefaultValueFromSchema(fieldSchema);

  return currentFieldValue ?? defaultValueFromProfile ?? defaultValueFromSchema ?? null;
};

export type GetObjectDefaultValueFromSchema =
  | components["schemas"]["AttributeSchema-Output"]
  | components["schemas"]["RelationshipSchema-Output"];

const getDefaultValueFromSchema = (fieldSchema: GetObjectDefaultValueFromSchema) => {
  if (fieldSchema.kind === "Boolean" || fieldSchema.kind === "Checkbox") {
    return !!fieldSchema.default_value;
  }

  return "default_value" in fieldSchema ? fieldSchema.default_value : null;
};
