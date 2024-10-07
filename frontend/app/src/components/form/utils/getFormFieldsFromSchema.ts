import { ProfileData } from "@/components/form/object-form";
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
import { getFieldDefaultValue } from "@/components/form/utils/getFieldDefaultValue";
import { getRelationshipDefaultValue } from "@/components/form/utils/getRelationshipDefaultValue";
import { getRelationshipParent } from "@/components/form/utils/getRelationshipParent";
import { getRelationshipsForForm } from "@/components/form/utils/getRelationshipsForForm";
import { isFieldDisabled } from "@/components/form/utils/isFieldDisabled";
import { isRequired } from "@/components/form/utils/validation";
import { SCHEMA_ATTRIBUTE_KIND } from "@/config/constants";
import { AuthContextType } from "@/hooks/useAuth";
import { SchemaAttributeType } from "@/screens/edit-form-hook/dynamic-control-types";
import { store } from "@/state";
import { genericsState, iGenericSchema, iNodeSchema, schemaState } from "@/state/atoms/schema.atom";
import { sortByOrderWeight } from "@/utils/common";
import { AttributeType, RelationshipType } from "@/utils/getObjectItemDisplayValue";
import { getRelationshipOptions } from "@/utils/getSchemaObjectColumns";

type GetFormFieldsFromSchema = {
  schema: iNodeSchema | iGenericSchema;
  profiles?: Array<ProfileData>;
  initialObject?: Record<string, AttributeType | RelationshipType>;
  auth?: AuthContextType;
  isFilterForm?: boolean;
  pools?: Array<NumberPoolData>;
  isUpdate?: boolean;
};

export const getFormFieldsFromSchema = ({
  schema,
  profiles,
  initialObject,
  auth,
  isFilterForm,
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
          value: choice.name,
          label: choice.label ?? choice.name,
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
        items: attribute.enum,
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

  return formFields;
};
