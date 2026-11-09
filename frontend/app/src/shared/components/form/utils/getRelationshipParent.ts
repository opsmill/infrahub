import type { NodeRelationship } from "@/entities/nodes/object/domain/model/node";

export const getRelationshipParent = (relationshipData: NodeRelationship | undefined) => {
  if (!relationshipData) return;

  if ("edges" in relationshipData) return;

  return relationshipData.node?.__typename;
};
