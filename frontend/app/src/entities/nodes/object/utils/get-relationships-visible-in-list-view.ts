import type { RelationshipSchema } from "@/entities/schema/types";

export function getRelationshipsVisibleInListView(
  relationships: RelationshipSchema[]
): RelationshipSchema[] {
  return relationships.filter((relationship) => {
    switch (relationship.kind) {
      case "Attribute":
      case "Parent":
        return true;
      case "Hierarchy":
        return relationship.cardinality === "one";
      default:
        return false;
    }
  });
}
