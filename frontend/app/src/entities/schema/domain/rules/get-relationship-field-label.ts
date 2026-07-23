import type { ModelSchema, RelationshipSchema } from "@/entities/schema/domain/model/schema";
import { isGenericSchema } from "@/entities/schema/domain/rules/is-generic-schema";

export const getRelationshipFieldLabel = (
  relationshipSchema: RelationshipSchema,
  peerSchema?: ModelSchema | null
): string => {
  if (relationshipSchema.hierarchical && peerSchema?.label && !isGenericSchema(peerSchema)) {
    return peerSchema.label;
  }

  return relationshipSchema.label ?? relationshipSchema.name;
};
