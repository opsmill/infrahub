import { DynamicFieldProps } from "./type";
import { iNodeSchema } from "@/state/atoms/schema.atom";
import { SchemaAttributeType } from "@/screens/edit-form-hook/dynamic-control-types";
import { sortByOrderWeight } from "@/utils/common";
import { SCHEMA_ATTRIBUTE_KIND } from "@/config/constants";
import {
  getFieldValue,
  getObjectRelationshipsForForm,
  getRelationshipValue,
  getSelectParent,
} from "@/utils/getSchemaObjectColumns";
import { AttributeType } from "@/utils/getObjectItemDisplayValue";

type GetFormFieldsFromSchema = {
  schema: iNodeSchema;
  profile?: Object;
  initialObject?: Record<string, AttributeType>;
};

export const getFormFieldsFromSchema = ({
  schema,
  profile,
  initialObject,
}: GetFormFieldsFromSchema): Array<DynamicFieldProps> => {
  const unorderedFields = [
    ...(schema.attributes ?? []),
    ...getObjectRelationshipsForForm(schema),
  ].filter((attribute) => !attribute.read_only);
  const orderedFields: typeof unorderedFields = sortByOrderWeight(unorderedFields);

  return orderedFields.map((attribute) => {
    if ("peer" in attribute) {
      return {
        name: attribute.name,
        label: attribute.label ?? undefined,
        type: "relationship",
        defaultValue: getRelationshipValue({ field: attribute, row: initialObject }),
        description: attribute.description ?? undefined,
        parent: getSelectParent(initialObject, attribute),
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
        rules: {
          required: !attribute.optional,
        },
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
        name: attribute.name,
        label: attribute.label ?? undefined,
        type: "enum",
        defaultValue: getFieldValue({ field: attribute, row: initialObject, profile }),
        unique: attribute.unique,
        description: attribute.description ?? undefined,
        rules: {
          required: !attribute.optional,
        },
        items: attribute.enum as string[],
      };
    }

    return {
      name: attribute.name,
      label: attribute.label ?? undefined,
      defaultValue: getFieldValue({ field: attribute, row: initialObject, profile }),
      description: attribute.description ?? undefined,
      type: attribute.kind as Exclude<SchemaAttributeType, "Dropdown">,
      unique: attribute.unique,
      rules: {
        required: !attribute.optional,
      },
    };
  });
};
