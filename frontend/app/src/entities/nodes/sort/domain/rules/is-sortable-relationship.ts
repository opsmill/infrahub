import type { RelationshipSchema } from "@/entities/schema/domain/model/schema";

/** A node can only be sorted through cardinality-one relationships. */
export function isSortableRelationship(relationship: RelationshipSchema): boolean {
  return relationship.cardinality === "one";
}
