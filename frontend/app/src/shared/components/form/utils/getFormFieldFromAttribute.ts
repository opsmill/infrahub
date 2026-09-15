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

import type { AuthContextType } from "@/entities/authentication/ui/auth-provider";
import type { AttributeType } from "@/entities/nodes/getObjectItemDisplayValue";
import type {
  NodeAttributeWithMetadata,
  NodeObject,
} from "@/entities/nodes/object/domain/model/node";
import type { NumberPool } from "@/entities/resource-manager/domain/model/number-pool";
import { NUMBER_POOL_KIND } from "@/entities/resource-manager/domain/model/pool";
import { getPoolKindFromSchema } from "@/entities/resource-manager/domain/rules/get-pool-kind-from-schema";
import { ATTRIBUTE_KIND } from "@/entities/schema/domain/model/attribute-kind";
import type {
  AttributeKind,
  AttributeSchema,
  ModelSchema,
  NumberAttributeParameters,
  TextAttributeParameters,
} from "@/entities/schema/domain/model/schema";
import { validateIpAddressAttribute } from "@/entities/schema/domain/rules/validation/validate-ip-address-attribute";
import { validateNumberAttribute } from "@/entities/schema/domain/rules/validation/validate-number-attribute";
import { validateTextAttribute } from "@/entities/schema/domain/rules/validation/validate-text-attribute";

export const getFormFieldFromAttribute = ({
  auth,
  isDefaultBranch,
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
  isDefaultBranch: boolean | undefined;
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
      initialObject: currentObject as Record<string, NodeAttributeWithMetadata> | undefined,
      objectTemplate,
      profiles,
      isFilterForm,
    }),
    description: attributeSchema.description ?? undefined,
    isBulkUpdate,
    attribute: attributeSchema,
    disabled: isFieldDisabled({
      auth,
      isDefaultBranch,
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

        // IPAddress has no parameters, so this check sits outside the block above
        if (attributeKind === ATTRIBUTE_KIND.IP_ADDRESS) {
          const validation = validateIpAddressAttribute(
            { isRequired: !attributeSchema.optional },
            formFieldValue.value as string | null
          );
          return validation.success || validation.error;
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
        (choice: components["schemas"]["DropdownChoiceRead"]) => ({
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
    const numberPools = pools?.filter((pool) => pool.attributeName === attributeSchema.name) ?? [];

    const fromPoolName = `${attributeSchema.name}${FROM_RESOURCE_POOL_SUFFIX}`;
    const hasFromPoolRelationship = schema.relationships?.some((r) => r.name === fromPoolName);

    // A number attribute reaches a pool by two independent routes: a template's schema grows a
    // `<name>_from_resource_pool` relationship, while on a plain node the only evidence is a
    // CoreNumberPool configured for this kind and attribute. Both land on `pool` — the shape
    // every other pool-backed field already uses — so one gate drives the value-or-pool tabs
    // everywhere. `fromPoolRelationshipName` stays keyed to the relationship alone, because
    // that is what decides where a pool value is submitted.
    const numberField: DynamicNumberFieldProps = {
      ...basicFormFieldProps,
      type: "Number",
      pool:
        hasFromPoolRelationship || numberPools.length
          ? {
              kind: NUMBER_POOL_KIND,
              defaultAllocatedObjectKind: schema.kind!,
              fromPoolRelationshipName: hasFromPoolRelationship ? fromPoolName : undefined,
              // Pre-fetched rather than queried: CoreNumberPool has to be narrowed to this
              // node kind and attribute, which the caller already did.
              options: numberPools,
            }
          : undefined,
    };

    return numberField;
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
