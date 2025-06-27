import { AuthContextType } from "@/entities/authentication/ui/useAuth";
import { RelationshipType } from "@/entities/nodes/getObjectItemDisplayValue";
import { NodeObject, NodeRelationship } from "@/entities/nodes/types";
import { ModelSchema, RelationshipSchema } from "@/entities/schema/types";
import {
  DynamicRelationshipFieldProps,
  FormRelationshipValue,
} from "@/shared/components/form/type";
import { getRelationshipDefaultValue } from "@/shared/components/form/utils/getRelationshipDefaultValue";
import { getRelationshipParent } from "@/shared/components/form/utils/getRelationshipParent";
import { isFieldDisabled } from "@/shared/components/form/utils/isFieldDisabled";
import { isMaxCount, isMinCount, isRequired } from "@/shared/components/form/utils/validation";

interface GetFormFieldFromRelationshipParams {
  auth?: AuthContextType;
  isFilterForm: boolean;
  relationshipSchema: RelationshipSchema;
  relationshipData: RelationshipType;
  objectTemplate?: NodeObject | null;
  schema: ModelSchema;
  parentSchema: ModelSchema;
  parentData?: NodeObject | null;
}

export const getFormFieldFromRelationship = ({
  relationshipSchema,
  relationshipData,
  objectTemplate,
  isFilterForm = false,
  schema,
  parentSchema,
  parentData,
  auth,
}: GetFormFieldFromRelationshipParams): DynamicRelationshipFieldProps => {
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
      schema,
      parentSchema,
      parentData,
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
      validate: {
        required: (formFieldValue: FormRelationshipValue) => {
          if (isFilterForm || relationshipSchema.optional) return true;

          return isRequired(formFieldValue) || "Required";
        },
        maxCount: (formFieldValue: FormRelationshipValue) => {
          if (isFilterForm) return true;
          return isMaxCount(relationshipSchema.max_count)(formFieldValue);
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
