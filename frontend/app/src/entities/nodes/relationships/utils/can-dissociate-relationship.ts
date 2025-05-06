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

  // If bidirectional (if it's not defined then it's the default value), check from the peer point of view
  if (
    (!parentRelationship?.direction || parentRelationship?.direction === "bidirectional") &&
    peerRelationship
  ) {
    return parentRelationship?.optional && peerRelationship?.optional;
  }

  // Check if it's optionnal or there is enough peers
  return (
    !!parentRelationship?.optional || relationshipsCount > (parentRelationship?.min_count ?? 1)
  );
}
