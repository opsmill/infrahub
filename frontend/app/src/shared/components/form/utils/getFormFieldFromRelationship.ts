import type {
  DynamicRelationshipFieldProps,
  FormRelationshipValue,
  RelationshipFieldType,
} from "@/shared/components/form/type";
import { getRelationshipDefaultValue } from "@/shared/components/form/utils/getRelationshipDefaultValue";
import { getRelationshipParent } from "@/shared/components/form/utils/getRelationshipParent";
import { isFieldDisabled } from "@/shared/components/form/utils/isFieldDisabled";
import { isRequired } from "@/shared/components/form/utils/validation";

import type { AuthContextType } from "@/entities/authentication/ui/useAuth";
import type { RelationshipType } from "@/entities/nodes/getObjectItemDisplayValue";
import type { NodeObject, NodeRelationship } from "@/entities/nodes/types";
import type { ModelSchema, RelationshipSchema } from "@/entities/schema/types";
import { validateRelationshipMany } from "@/entities/schema/utils/validation/validate-relationship-many";

interface GetFieldLabelParams {
  type?: RelationshipFieldType;
  relationshipSchema: RelationshipSchema;
}

const getFieldLabel = ({ type, relationshipSchema }: GetFieldLabelParams) => {
  const label = relationshipSchema.label ?? relationshipSchema.name;

  if (type === "relationship-add") {
    return `Add ${label}`;
  }

  if (type === "relationship-remove") {
    return `Remove ${label}`;
  }

  return label;
};

interface GetFormFieldFromRelationshipParams {
  type?: RelationshipFieldType;
  name?: string;
  auth?: AuthContextType;
  isFilterForm: boolean;
  isBulkUpdate?: boolean;
  relationshipSchema: RelationshipSchema;
  relationshipData?: RelationshipType;
  objectTemplate?: NodeObject | null;
  schema: ModelSchema;
  parentSchema: ModelSchema | null;
  parentData?: NodeObject | null;
}

export const getFormFieldFromRelationship = ({
  type,
  name,
  relationshipSchema,
  relationshipData,
  objectTemplate,
  isFilterForm = false,
  isBulkUpdate,
  schema,
  parentSchema,
  parentData,
  auth,
}: GetFormFieldFromRelationshipParams): DynamicRelationshipFieldProps => {
  const label = getFieldLabel({ type, relationshipSchema });

  const relationshipTemplate = objectTemplate?.[relationshipSchema.name] as
    | NodeRelationship
    | undefined;

  return {
    type: type ?? "relationship",
    name: name ?? relationshipSchema.name,
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
    isBulkUpdate,
    relationship: relationshipSchema,
    disabled: isFieldDisabled({
      auth,
      owner: undefined,
      isProtected: undefined,
      permissions: undefined, // Permissions are not supported for relationships yet
      isReadOnly: relationshipSchema.read_only,
    }),
    parent: getRelationshipParent(relationshipData ?? relationshipTemplate),
    rules: {
      required: !isFilterForm && !isBulkUpdate && !relationshipSchema.optional,
      validate: (formFieldValue: FormRelationshipValue) => {
        if (isFilterForm || isBulkUpdate) return true;

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
