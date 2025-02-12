import { AuthContextType } from "@/entities/authentication/ui/useAuth";
import { RelationshipType } from "@/entities/nodes/getObjectItemDisplayValue";
import { IModelSchema } from "@/entities/schema/stores/schema.atom";
import { RelationshipSchema } from "@/entities/schema/types";
import {
  DynamicRelationshipFieldProps,
  FormRelationshipValue,
} from "@/shared/components/form/type";
import { getRelationshipDefaultValue } from "@/shared/components/form/utils/getRelationshipDefaultValue";
import { getRelationshipParent } from "@/shared/components/form/utils/getRelationshipParent";
import { isFieldDisabled } from "@/shared/components/form/utils/isFieldDisabled";
import { isMinCount, isRequired } from "@/shared/components/form/utils/validation";

export const getFormFieldFromRelationship = ({
  relationshipSchema,
  relationshipData,
  isFilterForm = false,
  schema,
  auth,
}: {
  auth: AuthContextType | undefined;
  isFilterForm: boolean;
  relationshipSchema: RelationshipSchema;
  relationshipData: RelationshipType | undefined;
  schema: IModelSchema;
}): DynamicRelationshipFieldProps => {
  const label = relationshipSchema.label ?? relationshipSchema.name;
  return {
    type: "relationship",
    name: relationshipSchema.name,
    label,
    defaultValue: getRelationshipDefaultValue({
      relationshipData,
      isFilterForm,
    }),
    description: relationshipSchema.description ?? undefined,
    disabled: isFieldDisabled({
      auth,
      owner: undefined,
      isProtected: undefined,
      permissions: undefined, // Permissions are not supported for relationships yet
      isReadOnly: relationshipSchema.read_only,
    }),
    parent: getRelationshipParent(relationshipData),
    relationship: relationshipSchema,
    rules: {
      required: !isFilterForm && !relationshipSchema.optional,
      validate: {
        required: (formFieldValue: FormRelationshipValue) => {
          if (isFilterForm || relationshipSchema.optional) return true;

          return isRequired(formFieldValue) || "Required";
        },
        maxCount: (formFieldValue: FormRelationshipValue) => {
          const { max_count } = relationshipSchema;
          if (isFilterForm || max_count === 0 || !Array.isArray(formFieldValue.value)) {
            return true;
          }

          return formFieldValue.value.length <= max_count || `Maximum ${max_count} allowed`;
        },
        minCount: (formFieldValue: FormRelationshipValue) => {
          if (isFilterForm) return true;
          return isMinCount(relationshipSchema.min_count)(formFieldValue);
        },
      },
    },
    schema,
  };
};
