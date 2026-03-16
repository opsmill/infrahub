import { isFromResourcePoolRelationship } from "@/entities/nodes/object/utils/is-from-resource-pool-relationship";
import type { RelationshipSchema } from "@/entities/schema/types";

export function getRelationshipsVisibleInListView(
  relationships: RelationshipSchema[]
): RelationshipSchema[] {
  return relationships.filter((relationship) => {
    switch (relationship.kind) {
      case "Attribute":
      case "Parent":
        return true;
      case "Generic":
        return isFromResourcePoolRelationship(relationship.name); // to get data from _resource_from_pool relationships but will be hidden in UI
      case "Hierarchy":
        return relationship.cardinality === "one";
      default:
        return false;
    }
  });
}
