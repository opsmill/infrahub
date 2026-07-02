import { IP_PREFIX_RELATIONSHIP_NAME } from "@/entities/ipam/constants";
import { getRelationshipsVisibleInListView } from "@/entities/nodes/object/domain/rules/get-relationships-visible-in-list-view";
import type { RelationshipSchema } from "@/entities/schema/domain/model/types";

export function getIpAddressRelationshipsVisibleInListView(
  relationships: Array<RelationshipSchema>
): Array<RelationshipSchema> {
  const ipPrefixRelationshipSchema = relationships.find(
    (relationship) => relationship.name === IP_PREFIX_RELATIONSHIP_NAME
  );

  const otherRelationshipSchema = getRelationshipsVisibleInListView(relationships);

  return ipPrefixRelationshipSchema
    ? [ipPrefixRelationshipSchema, ...otherRelationshipSchema]
    : otherRelationshipSchema;
}
