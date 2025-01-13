import { RelationshipType } from "@/entities/nodes/getObjectItemDisplayValue";

export const getRelationshipParent = (relationshipData: RelationshipType | undefined) => {
  if (!relationshipData) return undefined;

  if ("edges" in relationshipData) return undefined;

  return relationshipData.node?.__typename;
};
