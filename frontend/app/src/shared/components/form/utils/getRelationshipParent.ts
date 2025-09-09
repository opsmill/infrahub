import { RelationshipType } from "@/entities/nodes/getObjectItemDisplayValue";
import { NodeRelationship } from "@/entities/nodes/types";

export const getRelationshipParent = (
  relationshipData: RelationshipType | NodeRelationship | undefined
) => {
  if (!relationshipData) return;

  if ("edges" in relationshipData) return;

  return relationshipData.node?.__typename;
};
