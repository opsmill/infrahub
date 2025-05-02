import { NodeSchema } from "@/entities/schema/types";

export function getDissociateAction({
  parentKind,
  relationshipName,
  parentSchema,
  peerSchema,
  relationshipsCount,
}: {
  parentKind: string;
  relationshipName: string;
  parentSchema: NodeSchema | null;
  peerSchema: NodeSchema | null;
  relationshipsCount: number;
}) {
  const parentRelationship = parentSchema?.relationships?.find((relationship) => {
    return relationship.name === relationshipName;
  });

  const peerRelationship = peerSchema?.relationships?.find((relationship) => {
    return (
      relationship.peer === parentKind && relationship.direction === parentRelationship?.direction
    );
  });

  // If bidirectional, check from the peer point of view
  if (parentRelationship?.direction === "bidirectional" && peerRelationship) {
    return parentRelationship?.optional && peerRelationship?.optional;
  }

  // Check if it's optionnal or there is enough peers
  return parentRelationship?.optional || relationshipsCount > (parentRelationship?.min_count ?? 1);
}
