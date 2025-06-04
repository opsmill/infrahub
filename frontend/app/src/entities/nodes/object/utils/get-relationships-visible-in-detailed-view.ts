import { RelationshipSchema } from "@/entities/schema/types";

export function getRelationshipsVisibleInDetailedView(
  relationships: RelationshipSchema[]
): RelationshipSchema[] {
  return relationships.filter((relationship) => {
    switch (relationship.kind) {
      case "Attribute":
      case "Parent": {
        return true;
      }
      case "Component":
      case "Generic":
      case "Hierarchy": {
        return relationship.cardinality === "one";
      }
      default: {
        return false;
      }
    }
  });
}
