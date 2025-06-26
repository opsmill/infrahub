import type { AuthContextType } from "@/entities/authentication/ui/useAuth";
import type { RelationshipType } from "@/entities/nodes/getObjectItemDisplayValue";
import type { NodeObject, NodeRelationship } from "@/entities/nodes/types";
import type { ModelSchema, RelationshipSchema } from "@/entities/schema/types";
import { validateRelationshipMany } from "@/entities/schema/utils/validation/validate-relationship-many";
import type {
  DynamicRelationshipFieldProps,
  FormRelationshipValue,
} from "@/shared/components/form/type";
import { getRelationshipDefaultValue } from "@/shared/components/form/utils/getRelationshipDefaultValue";
import { getRelationshipParent } from "@/shared/components/form/utils/getRelationshipParent";
import { isFieldDisabled } from "@/shared/components/form/utils/isFieldDisabled";
import { isRequired } from "@/shared/components/form/utils/validation";

export const getFormFieldFromRelationship = ({
  relationshipSchema,
  relationshipData,
  objectTemplate,
  isFilterForm = false,
  schema,
  auth,
}: {
  auth: AuthContextType | undefined;
  isFilterForm: boolean;
  relationshipSchema: RelationshipSchema;
  relationshipData: RelationshipType | undefined;
  objectTemplate: NodeObject | null | undefined;
  schema: ModelSchema;
}): DynamicRelationshipFieldProps => {
  const label = relationshipSchema.label ?? relationshipSchema.name;
  const relationshipTemplate = objectTemplate?.[relationshipSchema.name] as
    | NodeRelationship
    | undefined;
  return {
    type: "relationship",
    name: relationshipSchema.name,
    label,
    defaultValue: getRelationshipDefaultValue({
      relationshipData,
      objectTemplate,
      isFilterForm,
      relationshipName: relationshipSchema.name,
    }),
    description: relationshipSchema.description ?? undefined,
    disabled: isFieldDisabled({
      auth,
      owner: undefined,
      isProtected: undefined,
      permissions: undefined, // Permissions are not supported for relationships yet
      isReadOnly: relationshipSchema.read_only,
    }),
    parent: getRelationshipParent(relationshipData ?? relationshipTemplate),
    relationship: relationshipSchema,
    rules: {
      required: !isFilterForm && !relationshipSchema.optional,
      validate: (formFieldValue: FormRelationshipValue) => {
        if (isFilterForm) return true;

        if (relationshipSchema.cardinality === "many") {
          const validation = validateRelationshipMany(
            {
              isRequired: !relationshipSchema.optional,
              minCount: relationshipSchema.min_count,
              maxCount: relationshipSchema.max_count,
            },
            formFieldValue.value
          );
          return validation.success || validation.error;
        }

        if (relationshipSchema.optional) return true;
        return isRequired(formFieldValue) || "Required";
      },
    },
    schema,
  };
};
