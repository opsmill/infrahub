import { isFromResourcePoolRelationship } from "@/entities/nodes/object/domain/rules/is-from-resource-pool-relationship";
import type { RelationshipSchema } from "@/entities/schema/domain/model/schema";

/**
 * `revealedNames` opts specific `display: "extra"` relationships back in without relaxing the kind
 * switch below: a revealed relationship the list view cannot render stays excluded. It defaults to
 * the empty set, which reveals nothing — so a caller with nothing to reveal simply omits it.
 */
export function getRelationshipsVisibleInListView(
  relationships: RelationshipSchema[],
  revealedNames: ReadonlySet<string> = new Set()
): RelationshipSchema[] {
  return relationships.filter((relationship) => {
    if (relationship.display === "extra" && !revealedNames.has(relationship.name)) return false;

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
