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
  DynamicNumberFieldProps,
  DynamicRelationshipFieldProps,
  FormFieldValue,
  NumberPoolData,
} from "@/components/form/type";
import { getOptionsFromAttribute, getRelationshipOptions } from "@/utils/getSchemaObjectColumns";
import { isGeneric, sortByOrderWeight } from "@/utils/common";
import { getFieldDefaultValue } from "@/components/form/utils/getFieldDefaultValue";
import { SchemaAttributeType } from "@/screens/edit-form-hook/dynamic-control-types";
import { store } from "@/state";
import { SCHEMA_ATTRIBUTE_KIND } from "@/config/constants";
import { ProfileData } from "@/components/form/object-form";
import { isFieldDisabled } from "@/components/form/utils/isFieldDisabled";
import { getRelationshipDefaultValue } from "@/components/form/utils/getRelationshipDefaultValue";
import { Filter } from "@/hooks/useFilters";
import { getRelationshipParent } from "@/components/form/utils/getRelationshipParent";
import { isRequired } from "@/components/form/utils/validation";
import { getRelationshipsForForm } from "@/components/form/utils/getRelationshipsForForm";

type GetFormFieldsFromSchema = {
  schema: iNodeSchema | iGenericSchema;
  profiles?: Array<ProfileData>;
  initialObject?: Record<string, AttributeType | RelationshipType>;
  auth?: AuthContextType;
  isFilterForm?: boolean;
  filters?: Array<Filter>;
  pools?: Array<NumberPoolData>;
  isUpdate?: boolean;
};

export const getFormFieldsFromSchema = ({
  schema,
  profiles,
  initialObject,
  auth,
  isFilterForm,
  filters,
  pools = [],
  isUpdate,
}: GetFormFieldsFromSchema): Array<DynamicFieldProps> => {
  const unorderedFields = [
    ...(schema.attributes ?? []),
    ...getRelationshipsForForm(schema.relationships ?? [], isUpdate),
  ].filter((attribute) => !attribute.read_only);
  const orderedFields: typeof unorderedFields = sortByOrderWeight(unorderedFields);

  const formFields: Array<DynamicFieldProps> = orderedFields.map((attribute) => {
    const currentFieldValue = initialObject
      ? (initialObject[attribute.name] as AttributeType)
      : null;

    const basicFomFieldProps: DynamicInputFieldProps = {
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
        validate: {
          required: (formFieldValue: FormFieldValue) => {
            if (isFilterForm || attribute.optional) return true;

            return isRequired(formFieldValue);
          },
        },
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

    if (Array.isArray(attribute.enum)) {
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

    if (attribute.kind === SCHEMA_ATTRIBUTE_KIND.NUMBER) {
      const numberPools = pools?.filter((pool) => pool.nodeAttribute.name === attribute.name);

      const dropdownField: DynamicNumberFieldProps = {
        ...basicFomFieldProps,
        type: "Number",
        unique: attribute.unique,
        pools: numberPools,
      };

      return dropdownField;
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
    const nodes = store.get(schemaState);
    const profiles = store.get(profilesAtom);
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
