import { genericsState, iGenericSchema, iNodeSchema, schemaState } from "@/state/atoms/schema.atom";
import { AttributeType } from "@/utils/getObjectItemDisplayValue";
import { AuthContextType } from "@/hooks/useAuth";
import { DynamicFieldProps } from "@/components/form/type";
import {
  getObjectRelationshipsForForm,
  getOptionsFromAttribute,
  getRelationshipOptions,
  getRelationshipValue,
  getSelectParent,
} from "@/utils/getSchemaObjectColumns";
import { sortByOrderWeight } from "@/utils/common";
import { getIsDisabled } from "@/utils/formStructureForCreateEdit";
import { getObjectDefaultValue } from "@/components/form/utils/getObjectDefaultValue";
import { SchemaAttributeType } from "@/screens/edit-form-hook/dynamic-control-types";
import { store } from "@/state";
import { SCHEMA_ATTRIBUTE_KIND } from "@/config/constants";

type GetFormFieldsFromSchema = {
  schema: iNodeSchema | iGenericSchema;
  schemas?: iNodeSchema[] | iGenericSchema[];
  profiles?: Object[];
  initialObject?: Record<string, AttributeType>;
  user?: AuthContextType;
  isFilterForm?: boolean;
  filters?: Array<any>;
};

export const getFormFieldsFromSchema = ({
  schema,
  schemas,
  profiles,
  initialObject,
  user,
  isFilterForm,
  filters,
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
        !!initialObject[attribute.name].is_protected,
      isReadOnly: attribute.read_only,
    });

    const basicFomFieldProps = {
      name: attribute.name,
      label: attribute.label ?? undefined,
      defaultValue: getObjectDefaultValue({
        fieldSchema: attribute,
        initialObject,
        profiles,
        isFilterForm,
      }),
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
    const kindFilter = filters?.find((filter) => filter.name == "kind__value");

    const items = schema.used_by
      .map((kind) => {
        if (!schemas) return null;

        const relatedSchema = schemas.find((schema) => schema.kind === kind);
        console.log("relatedSchema: ", relatedSchema);

        if (!relatedSchema) return null;

        return {
          id: relatedSchema.kind,
          name: relatedSchema.label ?? relatedSchema.name,
          badge: relatedSchema.namespace,
        };
      })
      .filter(Boolean);

    return [
      {
        name: "kind",
        label: "Kind",
        description: "Select a kind to filter nodes",
        type: "Dropdown",
        defaultValue: kindFilter?.value,
        items,
      },
      ...formFields,
    ];
  }

  return formFields;
};
