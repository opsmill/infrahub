import { DynamicFieldProps } from "./type";
import { genericsState, iNodeSchema, schemaState } from "@/state/atoms/schema.atom";
import { SchemaAttributeType } from "@/screens/edit-form-hook/dynamic-control-types";
import { sortByOrderWeight } from "@/utils/common";
import { SCHEMA_ATTRIBUTE_KIND } from "@/config/constants";
import {
  getFieldValue,
  getObjectRelationshipsForForm,
  getOptionsFromAttribute,
  getRelationshipOptions,
  getRelationshipValue,
  getSelectParent,
} from "@/utils/getSchemaObjectColumns";
import { AttributeType } from "@/utils/getObjectItemDisplayValue";
import { store } from "@/state";
import { getIsDisabled } from "@/utils/formStructureForCreateEdit";

type GetFormFieldsFromSchema = {
  schema: iNodeSchema;
  profile?: Object;
  initialObject?: Record<string, AttributeType>;
  user?: any;
};

export const getFormFieldsFromSchema = ({
  schema,
  profile,
  initialObject,
  user,
}: GetFormFieldsFromSchema): Array<DynamicFieldProps> => {
  const unorderedFields = [
    ...(schema.attributes ?? []),
    ...getObjectRelationshipsForForm(schema),
  ].filter((attribute) => !attribute.read_only);
  const orderedFields: typeof unorderedFields = sortByOrderWeight(unorderedFields);

  return orderedFields.map((attribute) => {
    const disabled = getIsDisabled({
      owner: initialObject && initialObject[attribute.name]?.owner,
      user,
      isProtected:
        initialObject &&
        initialObject[attribute.name] &&
        initialObject[attribute.name].is_protected,
      isReadOnly: attribute.read_only,
    });

    if ("peer" in attribute) {
      const nodes = store.get(schemaState);
      const generics = store.get(genericsState);

      return {
        name: attribute.name,
        label: attribute.label ?? undefined,
        type: "relationship",
        defaultValue: getRelationshipValue({ field: attribute, row: initialObject }),
        description: attribute.description ?? undefined,
        disabled,
        parent: getSelectParent(initialObject, attribute),
        options: getRelationshipOptions(initialObject, attribute, nodes, generics),
        rules: {
          required: !attribute.optional,
        },
        relationship: attribute,
        schema,
      };
    }

    if (attribute.kind === SCHEMA_ATTRIBUTE_KIND.DROPDOWN) {
      return {
        name: attribute.name,
        label: attribute.label ?? undefined,
        type: SCHEMA_ATTRIBUTE_KIND.DROPDOWN,
        defaultValue: getFieldValue({ field: attribute, row: initialObject, profile }),
        unique: attribute.unique,
        description: attribute.description ?? undefined,
        disabled,
        rules: {
          required: !attribute.optional,
        },
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
      const fieldValue = getFieldValue({ field: attribute, row: initialObject, profile });
      return {
        name: attribute.name,
        label: attribute.label ?? undefined,
        type: "enum",
        defaultValue: fieldValue,
        disabled,
        field: attribute,
        schema: schema,
        unique: attribute.unique,
        description: attribute.description ?? undefined,
        rules: {
          required: !attribute.optional,
        },
        items: getOptionsFromAttribute(attribute, fieldValue),
      };
    }

    return {
      name: attribute.name,
      label: attribute.label ?? undefined,
      defaultValue: getFieldValue({ field: attribute, row: initialObject, profile }),
      description: attribute.description ?? undefined,
      disabled,
      type: attribute.kind as Exclude<SchemaAttributeType, "Dropdown">,
      unique: attribute.unique,
      rules: {
        required: !attribute.optional,
      },
    };
  });
};
