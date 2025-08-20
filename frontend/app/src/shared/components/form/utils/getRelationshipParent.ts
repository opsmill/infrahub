import { RelationshipType } from "@/entities/nodes/getObjectItemDisplayValue";
import { NodeRelationship } from "@/entities/nodes/types";

export const getRelationshipParent = (
  relationshipData: RelationshipType | NodeRelationship | undefined
) => {
  if (!relationshipData) return undefined;

  if ("edges" in relationshipData) return undefined;

  return relationshipData.node?.__typename;
};
