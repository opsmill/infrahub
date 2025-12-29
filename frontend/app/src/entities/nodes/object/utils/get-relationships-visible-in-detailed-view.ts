import type { RelationshipSchema } from "@/entities/schema/types";

export function isRelationshipVisibleInDetailedView(
  relationshipSchema: RelationshipSchema
): boolean {
  switch (relationshipSchema.kind) {
    case "Attribute":
    case "Profile":
    case "Parent": {
      return true;
    }
    case "Component":
    case "Generic":
    case "Hierarchy": {
      return relationshipSchema.cardinality === "one";
    }
    case "Group": {
      return relationshipSchema.name === "member_of_groups";
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
