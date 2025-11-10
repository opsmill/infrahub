import type { RelationshipKind } from "@/entities/nodes/types";
import type { RelationshipSchema } from "@/entities/schema/types";

const RELATIONSHIP_KIND_VISIBLE_IN_TAB: Array<RelationshipKind> = [
  "Generic",
  "Component",
  "Hierarchy",
  "Template",
];

export function isRelationshipVisibleInTab(relationshipSchema: RelationshipSchema): boolean {
  if (relationshipSchema.cardinality === "one") {
    return false;
  }

  return RELATIONSHIP_KIND_VISIBLE_IN_TAB.includes(relationshipSchema.kind);
}

export function getRelationshipsVisibleInTab(
  relationships: RelationshipSchema[]
): RelationshipSchema[] {
  return relationships
    .filter(isRelationshipVisibleInTab)
    .sort((a, b) => (a.order_weight ?? 0) - (b.order_weight ?? 0));
}
