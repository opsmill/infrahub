import { ModelSchema } from "@/entities/schema/types";

export function canDissociateRelationship({
  relationshipName,
  parentSchema,
  peerSchema,
  relationshipsCount,
}: {
  relationshipName: string;
  parentSchema: ModelSchema;
  peerSchema: ModelSchema;
  relationshipsCount: number;
}) {
  const parentToPeerRelationship = parentSchema.relationships?.find((relationship) => {
    return relationship.name === relationshipName;
  });
  if (!parentToPeerRelationship) return false;

  const peerToParentRelationship = peerSchema.relationships?.find((relationship) => {
    const isSameDirection = relationship.direction === parentToPeerRelationship.direction;

    if ("inherit_from" in parentSchema) {
      return parentSchema.inherit_from?.includes(relationship.peer) && isSameDirection;
    }

    return relationship.peer === parentSchema.kind && isSameDirection;
  });

  const minCount = parentToPeerRelationship.min_count || 1;
  const isOptional = parentToPeerRelationship.optional;
  const hasEnoughPeers = relationshipsCount > minCount;

  if (!peerToParentRelationship) {
    return isOptional || hasEnoughPeers;
  }

  const isPeerOptional = peerToParentRelationship.optional;
  if (isOptional && isPeerOptional) {
    return true;
  }

  if (!isOptional) return hasEnoughPeers;
  return isPeerOptional;
}
