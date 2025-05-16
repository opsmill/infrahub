import { AuthContextType } from "@/entities/authentication/ui/useAuth";
import { AttributeType } from "@/entities/nodes/getObjectItemDisplayValue";
import { NodeObject } from "@/entities/nodes/types";
import { ATTRIBUTE_KIND } from "@/entities/schema/constants";
import { AttributeKind, AttributeSchema, ModelSchema } from "@/entities/schema/types";
import { components } from "@/shared/api/rest/types.generated";
import { ProfileData } from "@/shared/components/form/object-form";
import {
  DynamicAttributeFieldProps,
  DynamicDropdownFieldProps,
  DynamicEnumFieldProps,
  DynamicInputFieldProps,
  DynamicNumberFieldProps,
  FormFieldValue,
  NumberPoolData,
} from "@/shared/components/form/type";
import { getFieldDefaultValue } from "@/shared/components/form/utils/getFieldDefaultValue";
import { isFieldDisabled } from "@/shared/components/form/utils/isFieldDisabled";
import { isRequired } from "@/shared/components/form/utils/validation";

export const getFormFieldFromAttribute = ({
  auth,
  attributeSchema,
  currentObject,
  objectTemplate,
  schema,
  isFilterForm,
  pools,
  profiles,
}: {
  auth: AuthContextType | undefined;
  attributeSchema: AttributeSchema;
  currentObject: Record<string, AttributeType> | undefined;
  objectTemplate: NodeObject | null | undefined;
  schema: ModelSchema;
  isFilterForm: boolean;
  pools?: Array<NumberPoolData>;
  profiles?: Array<ProfileData>;
}): DynamicAttributeFieldProps => {
  const attributeData = currentObject?.[attributeSchema.name];

  const basicFomFieldProps: DynamicInputFieldProps = {
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
    rules: {
      required: !isFilterForm && !attributeSchema.optional,
      validate: {
        required: (formFieldValue: FormFieldValue) => {
          if (isFilterForm || attributeSchema.optional) return true;

          return isRequired(formFieldValue);
        },
      },
    },
  };

  if (attributeSchema.kind === ATTRIBUTE_KIND.DROPDOWN) {
    const dropdownField: DynamicDropdownFieldProps = {
      ...basicFomFieldProps,
      unique: attributeSchema.unique,
      type: ATTRIBUTE_KIND.DROPDOWN,
      field: attributeSchema,
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
      ...basicFomFieldProps,
      unique: attributeSchema.unique,
      type: "enum",
      field: attributeSchema,
      schema,
      items: attributeSchema.enum,
    };

    return enumField;
  }

  if (attributeSchema.kind === ATTRIBUTE_KIND.NUMBER) {
    const numberPools = pools?.filter((pool) => pool.nodeAttribute.name === attributeSchema.name);

    const dropdownField: DynamicNumberFieldProps = {
      ...basicFomFieldProps,
      unique: attributeSchema.unique,
      type: "Number",
      pools: numberPools,
    };

    return dropdownField;
  }

  return {
    ...basicFomFieldProps,
    unique: attributeSchema.unique,
  };
};
