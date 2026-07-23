import type { ModelSchema, RelationshipSchema } from "@/entities/schema/domain/model/schema";
import { isGenericSchema } from "@/entities/schema/domain/rules/is-generic-schema";

/**
 * Resolve the label to display for a relationship.
 *
 * For the auto-generated hierarchical `parent`/`children` relationships
 * (`hierarchical` is set to the hierarchy generic kind), surface the peer
 * kind's label (e.g. "Site") instead of the generic "Parent"/"Children" —
 * but only when the peer is a concrete node kind. When the peer resolves to
 * a generic, its label is too broad to be helpful, so we keep the generic
 * "Parent"/"Children" label. For every other relationship this is
 * behaviorally identical to the inline `label ?? name` expression it replaces.
 *
 * Pure: the peer schema is supplied by the caller, so there is no store
 * access and no side effects.
 */
export const getRelationshipFieldLabel = (
  relationshipSchema: RelationshipSchema,
  peerSchema?: ModelSchema | null
): string => {
  if (relationshipSchema.hierarchical && peerSchema?.label && !isGenericSchema(peerSchema)) {
    return peerSchema.label;
  }

  return relationshipSchema.label ?? relationshipSchema.name;
};
