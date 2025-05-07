import { NodeSchema } from "@/entities/schema/types";

export function canDissociateRelationship({
  relationshipName,
  parentSchema,
  peerSchema,
  relationshipsCount,
}: {
  relationshipName: string;
  parentSchema: NodeSchema | null;
  peerSchema: NodeSchema | null;
  relationshipsCount: number;
}) {
  const parentRelationship = parentSchema?.relationships?.find((relationship) => {
    return relationship.name === relationshipName;
  });

  const peerRelationship = peerSchema?.relationships?.find((relationship) => {
    if (parentSchema?.inherit_from?.length) {
      return (
        parentSchema.inherit_from.includes(relationship.peer) &&
        relationship.direction === parentRelationship?.direction
      );
    }

    return (
      relationship.peer === parentSchema?.kind &&
      relationship.direction === parentRelationship?.direction
    );
  });

  const minCount = parentRelationship?.min_count ?? 1;
  const isOptional = !!parentRelationship?.optional;
  const hasEnoughPeers = relationshipsCount > minCount;

  if (peerRelationship) {
    const isPeerOptional = !!peerRelationship?.optional;

    // Both relationships are optional
    if (isOptional && isPeerOptional) return true;

    // Relationship is mandatory but there is enough peers
    if (hasEnoughPeers) return true;

    return false;
  }

  // It's optional or there is enough peers
  return isOptional || hasEnoughPeers;
}
