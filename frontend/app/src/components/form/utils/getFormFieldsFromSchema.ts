import {
  genericsState,
  iGenericSchema,
  iNodeSchema,
  profilesAtom,
  schemaState,
} from "@/state/atoms/schema.atom";
import { AttributeType, RelationshipType } from "@/utils/getObjectItemDisplayValue";
import { AuthContextType } from "@/hooks/useAuth";
import {
  DynamicDropdownFieldProps,
  DynamicEnumFieldProps,
  DynamicFieldProps,
  DynamicInputFieldProps,
  DynamicRelationshipFieldProps,
} from "@/components/form/type";
import {
  getObjectRelationshipsForForm,
  getOptionsFromAttribute,
  getRelationshipOptions,
} from "@/utils/getSchemaObjectColumns";
import { isGeneric, sortByOrderWeight } from "@/utils/common";
import { getFieldDefaultValue } from "@/components/form/utils/getFieldDefaultValue";
import { SchemaAttributeType } from "@/screens/edit-form-hook/dynamic-control-types";
import { store } from "@/state";
import { SCHEMA_ATTRIBUTE_KIND } from "@/config/constants";
import { ProfileData } from "@/components/form/object-form";
import { isFieldDisabled } from "@/components/form/utils/isFieldDisabled";
import { useAtomValue } from "jotai/index";
import { getRelationshipDefaultValue } from "@/components/form/utils/getRelationshipDefaultValue";
import { Filter } from "@/hooks/useFilters";
import { getRelationshipParent } from "@/components/form/utils/getRelationshipParent";

type GetFormFieldsFromSchema = {
  schema: iNodeSchema | iGenericSchema;
  profiles?: Array<ProfileData>;
  initialObject?: Record<string, AttributeType | RelationshipType>;
  auth?: AuthContextType;
  isFilterForm?: boolean;
  filters?: Array<Filter>;
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
    const currentFieldValue = initialObject
      ? (initialObject[attribute.name] as AttributeType)
      : null;

    const basicFomFieldProps = {
      name: attribute.name,
      label: attribute.label ?? undefined,
      defaultValue: getFieldDefaultValue({
        fieldSchema: attribute,
        initialObject: initialObject as Record<string, AttributeType>,
        profiles,
        isFilterForm,
      }),
      description: attribute.description ?? undefined,
      disabled: isFieldDisabled({
        auth,
        owner: currentFieldValue?.owner,
        isProtected: !!currentFieldValue?.is_protected,
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

      const currentRelationshipData = initialObject?.[attribute.name] as
        | RelationshipType
        | undefined;

      const relationshipField: DynamicRelationshipFieldProps = {
        ...basicFomFieldProps,
        type: "relationship",
        defaultValue: getRelationshipDefaultValue({
          relationshipData: currentRelationshipData,
          isFilterForm,
        }),
        parent: getRelationshipParent(currentRelationshipData),
        options: getRelationshipOptions(initialObject, attribute, nodes, generics),
        relationship: attribute,
        schema,
      };

      return relationshipField;
    }

    if (attribute.kind === SCHEMA_ATTRIBUTE_KIND.DROPDOWN) {
      const dropdownField: DynamicDropdownFieldProps = {
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

      return dropdownField;
    }

    if (attribute.kind === SCHEMA_ATTRIBUTE_KIND.TEXT && Array.isArray(attribute.enum)) {
      const enumField: DynamicEnumFieldProps = {
        ...basicFomFieldProps,
        type: "enum",
        field: attribute,
        schema: schema,
        unique: attribute.unique,
        items: getOptionsFromAttribute(attribute, basicFomFieldProps.defaultValue),
      };

      return enumField;
    }

    const field: DynamicInputFieldProps = {
      ...basicFomFieldProps,
      unique: attribute.unique,
    };

    return field;
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

    const genericKindField: DynamicDropdownFieldProps = {
      name: "kind",
      label: "Kind",
      description: "Select a kind to filter nodes",
      type: "Dropdown",
      defaultValue: kindFilter ? { source: { type: "user" }, value: kindFilter.value } : undefined,
      items,
    };

    return [genericKindField, ...formFields];
  }

  return formFields;
};
