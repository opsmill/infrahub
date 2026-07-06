import { isRelationshipVisibleInDetailedView } from "@/entities/nodes/object/domain/rules/get-relationships-visible-in-detailed-view";
import { isFromResourcePoolRelationship } from "@/entities/nodes/object/domain/rules/is-from-resource-pool-relationship";
import type { RelationshipSchema } from "@/entities/schema/domain/model/schema";

export function isRelationshipVisibleInSummary(relationship: RelationshipSchema): boolean {
  return (
    isRelationshipVisibleInDetailedView(relationship) &&
    relationship.name !== "member_of_groups" &&
    relationship.kind !== "Profile" &&
    !isFromResourcePoolRelationship(relationship.name)
  );
}
