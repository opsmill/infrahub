import { isFromResourcePoolRelationship } from "@/entities/nodes/object/utils/is-from-resource-pool-relationship";
import type { RelationshipKind } from "@/entities/nodes/types";
import type { RelationshipSchema } from "@/entities/schema/types";

const RELATIONSHIP_KIND_VISIBLE_IN_TAB: Array<RelationshipKind> = [
  "Generic",
  "Component",
  "Hierarchy",
  "Template",
];

export function isRelationshipVisibleInTab(relationshipSchema: RelationshipSchema): boolean {
  if (
    relationshipSchema.cardinality === "one" ||
    isFromResourcePoolRelationship(relationshipSchema.name)
  ) {
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
