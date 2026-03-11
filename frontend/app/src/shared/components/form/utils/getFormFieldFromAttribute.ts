import type { components } from "@/shared/api/rest/types.generated";
import { FROM_RESOURCE_POOL_SUFFIX } from "@/shared/components/form/constants";
import type { ProfileData } from "@/shared/components/form/object-form";
import type {
  DynamicAttributeFieldProps,
  DynamicDropdownFieldProps,
  DynamicEnumFieldProps,
  DynamicFieldProps,
  DynamicNumberFieldProps,
  FormFieldValue,
} from "@/shared/components/form/type";
import { getFieldDefaultValue } from "@/shared/components/form/utils/getFieldDefaultValue";
import { isFieldDisabled } from "@/shared/components/form/utils/isFieldDisabled";
import { isRequired } from "@/shared/components/form/utils/validation";

import type { AuthContextType } from "@/entities/authentication/ui/useAuth";
import type { AttributeType } from "@/entities/nodes/getObjectItemDisplayValue";
import type { NodeObject } from "@/entities/nodes/types";
import type { NumberPool } from "@/entities/resource-manager/domain/type";
import { getPoolKindFromSchema } from "@/entities/resource-manager/utils/get-pool-kind-from-schema";
import { ATTRIBUTE_KIND } from "@/entities/schema/constants";
import type {
  AttributeKind,
  AttributeSchema,
  ModelSchema,
  NumberAttributeParameters,
  TextAttributeParameters,
} from "@/entities/schema/types";
import { validateNumberAttribute } from "@/entities/schema/utils/validation/validate-number-attribute";
import { validateTextAttribute } from "@/entities/schema/utils/validation/validate-text-attribute";

export const getFormFieldFromAttribute = ({
  auth,
  attributeSchema,
  currentObject,
  objectTemplate,
  schema,
  isFilterForm,
  isUpdate,
  isBulkUpdate,
  pools,
  profiles,
}: {
  auth: AuthContextType | undefined;
  attributeSchema: AttributeSchema;
  currentObject: Record<string, AttributeType> | undefined;
  objectTemplate: NodeObject | null | undefined;
  schema: ModelSchema;
  isFilterForm: boolean;
  isUpdate: boolean;
  isBulkUpdate: boolean;
  pools?: Array<NumberPool>;
  profiles?: Array<ProfileData>;
}): DynamicAttributeFieldProps => {
  const attributeData = currentObject?.[attributeSchema.name];

  const basicFormFieldProps: DynamicFieldProps = {
    name: attributeSchema.name,
    label: attributeSchema.label ?? undefined,
    defaultValue: getFieldDefaultValue({
      fieldSchema: attributeSchema,
      initialObject: currentObject,
      objectTemplate,
      profiles,
      isFilterForm,
    }),
    description: attributeSchema.description ?? undefined,
    isBulkUpdate,
    attribute: attributeSchema,
    disabled: isFieldDisabled({
      auth,
      owner: attributeData?.owner,
      isProtected: !!attributeData?.is_protected,
      permissions: { update: attributeData?.permissions?.update_value },
      isReadOnly: attributeSchema.read_only,
    }),
    type:
      schema.namespace === "Core" && attributeSchema.name === "node_kind"
        ? "NodeKind"
        : (attributeSchema.kind as Exclude<AttributeKind, "Dropdown">),
    unique: attributeSchema.unique,
    rules: {
      required: !isFilterForm && !isBulkUpdate && !attributeSchema.optional,
      validate: (formFieldValue: FormFieldValue) => {
        if (isFilterForm || isBulkUpdate) return true;
        if (formFieldValue.source?.type === "pool") return true;

        const attributeKind = attributeSchema.kind as AttributeKind;

        if (attributeSchema.parameters) {
          if (attributeKind === ATTRIBUTE_KIND.TEXT) {
            const attributeParameters = attributeSchema.parameters as TextAttributeParameters;
            const validation = validateTextAttribute(
              {
                isRequired: !attributeSchema.optional,
                minLength: attributeParameters.min_length,
                maxLength: attributeParameters.max_length,
              },
              formFieldValue.value as string | null
            );
            return validation.success || validation.error;
          }

          if (attributeKind === ATTRIBUTE_KIND.NUMBER) {
            const attributeParameters = attributeSchema.parameters as NumberAttributeParameters;
            const validation = validateNumberAttribute(
              {
                isRequired: !attributeSchema.optional,
                min: attributeParameters.min_value,
                max: attributeParameters.max_value,
              },
              formFieldValue.value as number | null
            );
            return validation.success || validation.error;
          }
        }

        if (attributeSchema.optional) return true;
        return isRequired(formFieldValue);
      },
    },
  };

  if (attributeSchema.kind === ATTRIBUTE_KIND.DROPDOWN) {
    const dropdownField: DynamicDropdownFieldProps = {
      ...basicFormFieldProps,
      type: ATTRIBUTE_KIND.DROPDOWN,
      schema,
      items: (attributeSchema.choices ?? []).map(
        (choice: components["schemas"]["DropdownChoice"]) => ({
          value: choice.name,
          label: choice.label ?? choice.name,
          color: choice.color ?? undefined,
          description: choice.description ?? undefined,
        })
      ),
    };

    return dropdownField;
  }

  if (Array.isArray(attributeSchema.enum)) {
    const enumField: DynamicEnumFieldProps = {
      ...basicFormFieldProps,
      type: "enum",
      schema,
      items: attributeSchema.enum,
    };

    return enumField;
  }

  if (attributeSchema.kind === ATTRIBUTE_KIND.NUMBER) {
    const numberPools = pools?.filter((pool) => pool.attributeName === attributeSchema.name);

    const fromPoolName = `${attributeSchema.name}${FROM_RESOURCE_POOL_SUFFIX}`;
    const hasFromPoolRelationship = schema.relationships?.some((r) => r.name === fromPoolName);

    const dropdownField: DynamicNumberFieldProps = {
      ...basicFormFieldProps,
      type: "Number",
      pools: numberPools,
      pool: hasFromPoolRelationship
        ? {
            kind: "CoreNumberPool",
            defaultAllocatedObjectKind: schema.kind as string,
            fromPoolRelationshipName: fromPoolName,
          }
        : undefined,
    };

    return dropdownField;
  }

  if (isUpdate) {
    return basicFormFieldProps;
  }

  if (attributeSchema.name === "prefix" || attributeSchema.name === "address") {
    const poolKind = getPoolKindFromSchema(schema);
    if (poolKind) {
      return {
        ...basicFormFieldProps,
        pool: {
          kind: poolKind,
          defaultAllocatedObjectKind: schema.kind as string,
        },
      };
    }
  }

  return basicFormFieldProps;
};
