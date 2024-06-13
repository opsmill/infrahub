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
    if ("cardinality" in attribute) {
      return {
        name: attribute.name,
        label: attribute.label ?? undefined,
        type: "relationship",
        defaultValue: getRelationshipValue({ field: attribute, row: initialObject }),
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

    return {
      name: attribute.name,
      label: attribute.label ?? undefined,
      defaultValue: getFieldValue({ field: attribute, row: initialObject, profile }),
      type: attribute.kind as Exclude<SchemaAttributeType, "Dropdown">,
      rules: {
        required: !attribute.optional,
      },
    };
  });
};
