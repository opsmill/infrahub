import { AuthContextType } from "@/entities/authentication/ui/useAuth";
import { RelationshipType } from "@/entities/nodes/getObjectItemDisplayValue";
import { IModelSchema } from "@/entities/schema/stores/schema.atom";
import { RelationshipSchema } from "@/entities/schema/types";
import { DynamicRelationshipFieldProps, FormFieldValue } from "@/shared/components/form/type";
import { getRelationshipDefaultValue } from "@/shared/components/form/utils/getRelationshipDefaultValue";
import { getRelationshipParent } from "@/shared/components/form/utils/getRelationshipParent";
import { isFieldDisabled } from "@/shared/components/form/utils/isFieldDisabled";
import { isRequired } from "@/shared/components/form/utils/validation";

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
  return {
    type: "relationship",
    name: relationshipSchema.name,
    label: relationshipSchema.label ?? undefined,
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
        required: (formFieldValue: FormFieldValue) => {
          if (isFilterForm || relationshipSchema.optional) return true;

          return isRequired(formFieldValue);
        },
      },
    },
    schema,
  };
};
