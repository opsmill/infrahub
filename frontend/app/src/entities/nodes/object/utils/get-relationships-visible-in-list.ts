import { RelationshipSchema } from "@/entities/schema/types";

export function getRelationshipsVisibleInListView(
  relationships: RelationshipSchema[]
): RelationshipSchema[] {
  return relationships.filter((relationship) => {
    if (relationship.kind === "Attribute") return true;
    return relationship.kind === "Hierarchy" && relationship.cardinality === "one";
  });
}
