import { FROM_RESOURCE_POOL_SUFFIX } from "@/shared/components/form/constants";
import type { ProfileData } from "@/shared/components/form/object-form";
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
import type { NodeFieldsWithMetadata, NodeObject, NodeRelationship } from "@/entities/nodes/types";
import { getPoolKindFromSchema } from "@/entities/resource-manager/utils/get-pool-kind-from-schema";
import { getSchema } from "@/entities/schema/domain/get-schema";
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
  objectData?: NodeFieldsWithMetadata;
  objectTemplate?: NodeObject | null;
  profiles?: Array<ProfileData>;
  schema: ModelSchema;
  parentSchema?: ModelSchema | null;
  parentData?: NodeObject | null;
}

export const getFormFieldFromRelationship = ({
  type,
  name,
  relationshipSchema,
  objectData,
  objectTemplate,
  profiles,
  isFilterForm = false,
  isBulkUpdate,
  schema,
  parentSchema,
  parentData,
  auth,
}: GetFormFieldFromRelationshipParams): DynamicRelationshipFieldProps => {
  const label = getFieldLabel({ type, relationshipSchema });

  const relationshipData = objectData?.[relationshipSchema.name] as NodeRelationship | undefined;

  const relationshipTemplate = objectTemplate?.[relationshipSchema.name] as
    | NodeRelationship
    | undefined;

  const { schema: peerSchema } = getSchema(relationshipSchema.peer);
  const poolKind = peerSchema ? getPoolKindFromSchema(peerSchema) : null;

  const fromPoolName = `${relationshipSchema.name}${FROM_RESOURCE_POOL_SUFFIX}`;
  const hasFromPoolRelationship = schema.relationships?.some((r) => r.name === fromPoolName);

  return {
    type: type ?? "relationship",
    name: name ?? relationshipSchema.name,
    label,
    pool:
      poolKind && peerSchema
        ? {
            kind: poolKind,
            defaultAllocatedObjectKind: peerSchema.kind as string,
            ...(hasFromPoolRelationship ? { fromPoolRelationshipName: fromPoolName } : {}),
          }
        : undefined,
    defaultValue: getRelationshipDefaultValue({
      objectData,
      objectTemplate,
      profiles,
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
  };
};
