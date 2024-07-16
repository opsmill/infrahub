import {
  genericsState,
  iGenericSchema,
  iNodeSchema,
  profilesAtom,
  schemaState,
} from "@/state/atoms/schema.atom";
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
import { isGeneric, sortByOrderWeight } from "@/utils/common";
import { getFieldDefaultValue } from "@/components/form/utils/getFieldDefaultValue";
import { SchemaAttributeType } from "@/screens/edit-form-hook/dynamic-control-types";
import { store } from "@/state";
import { SCHEMA_ATTRIBUTE_KIND } from "@/config/constants";
import { ProfileData } from "@/components/form/object-form";
import { isFieldDisabled } from "@/components/form/utils/isFieldDisabled";
import { useAtomValue } from "jotai/index";

type GetFormFieldsFromSchema = {
  schema: iNodeSchema | iGenericSchema;
  profiles?: Array<ProfileData>;
  initialObject?: Record<string, AttributeType>;
  auth?: AuthContextType;
  isFilterForm?: boolean;
  filters?: Array<any>;
};

export const getFormFieldsFromSchema = ({
  schema,
  profiles,
  initialObject,
  auth,
  isFilterForm,
  filters,
}: GetFormFieldsFromSchema): Array<DynamicFieldProps> => {
  const unorderedFields = [
    ...(schema.attributes ?? []),
    ...getObjectRelationshipsForForm(schema),
  ].filter((attribute) => !attribute.read_only);
  const orderedFields: typeof unorderedFields = sortByOrderWeight(unorderedFields);

  const formFields: Array<DynamicFieldProps> = orderedFields.map((attribute) => {
    const basicFomFieldProps = {
      name: attribute.name,
      label: attribute.label ?? undefined,
      defaultValue: getFieldDefaultValue({
        fieldSchema: attribute,
        initialObject,
        profiles,
        isFilterForm,
      }),
      description: attribute.description ?? undefined,
      disabled: isFieldDisabled({
        owner: initialObject && initialObject[attribute.name]?.owner,
        auth,
        isProtected:
          initialObject &&
          initialObject[attribute.name] &&
          !!initialObject[attribute.name].is_protected,
        isReadOnly: attribute.read_only,
      }),
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
  if (isFilterForm && isGeneric(schema) && schema.used_by?.length) {
    const kindFilter = filters?.find((filter) => filter.name == "kind__value");
    const nodes = useAtomValue(schemaState);
    const profiles = useAtomValue(profilesAtom);
    const schemas = [...nodes, ...profiles];

    const items = schema.used_by
      .map((kind) => {
        if (!schemas) return null;

        const relatedSchema = schemas.find((schema) => schema.kind === kind);

        if (!relatedSchema) return null;

        return {
          id: relatedSchema.kind as string,
          name: relatedSchema.label ?? relatedSchema.name,
          badge: relatedSchema.namespace,
        };
      })
      .filter((n) => n !== null);

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
