import { RelationshipKind } from "@/entities/nodes/types";
import { RelationshipSchema } from "@/entities/schema/types";

const RELATIONSHIP_KIND_VISIBLE_IN_TAB: Array<RelationshipKind> = [
  "Generic",
  "Component",
  "Hierarchy",
  "Template",
];

export function getRelationshipsVisibleInTab(
  relationships: RelationshipSchema[]
): RelationshipSchema[] {
  return relationships.filter((relationship): boolean => {
    if (relationship.cardinality === "one") {
      return false;
    }

    return RELATIONSHIP_KIND_VISIBLE_IN_TAB.includes(relationship.kind);
  });
}
