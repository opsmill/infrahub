import type { RelationshipSchema } from "@/entities/schema/types";

export function isRelationshipVisibleInDetailedView(
  relationshipSchema: RelationshipSchema
): boolean {
  switch (relationshipSchema.kind) {
    case "Attribute":
    case "Parent": {
      return true;
    }
    case "Component":
    case "Generic":
    case "Hierarchy": {
      return relationshipSchema.cardinality === "one";
    }
    default: {
      return false;
    }
  }
}

export function getRelationshipsVisibleInDetailedView(
  relationships: RelationshipSchema[]
): RelationshipSchema[] {
  return relationships.filter(isRelationshipVisibleInDetailedView);
}
