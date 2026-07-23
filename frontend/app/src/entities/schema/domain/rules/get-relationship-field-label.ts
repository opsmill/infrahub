import type { ModelSchema, RelationshipSchema } from "@/entities/schema/domain/model/schema";
import { isGenericSchema } from "@/entities/schema/domain/rules/is-generic-schema";

export const getRelationshipFieldLabel = (
  relationshipSchema: RelationshipSchema,
  peerSchema?: ModelSchema | null
): string => {
  // hierarchical parent/children show the peer kind's label, but a generic peer's label is too broad to identify the kind
  if (relationshipSchema.hierarchical && peerSchema?.label && !isGenericSchema(peerSchema)) {
    return peerSchema.label;
  }

  return relationshipSchema.label ?? relationshipSchema.name;
};
