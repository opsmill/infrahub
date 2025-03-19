import { RELATIONSHIP_VIEW_BLACKLIST, relationshipKindForForm } from "@/config/constants";
import { IP_ADDRESS_GENERIC, IP_PREFIX_GENERIC } from "@/entities/ipam/constants";
import { RelationshipKind } from "@/entities/nodes/types";
import { ModelSchema, RelationshipSchema } from "@/entities/schema/types";
import { isOfKind } from "@/entities/schema/utils/is-of-kind";

export const getRelationshipsForForm = (
  relationships: Array<RelationshipSchema>,
  isUpdate?: boolean,
  schema?: ModelSchema
) => {
  // Filter relationships based on cardinality and kind for form inclusion
  // For create forms, include relationships with cardinality 'one', eligible kinds, or mandatory cardinality 'many'
  // For update forms, only include relationships with cardinality 'one' or those with eligible kinds (Attribute or Parent). Other should be display as tabs on details view
  return relationships.filter((relationship) => {
    if (relationship.cardinality === "one" && relationship.kind !== "Template") return true;

    if (schema && (isOfKind(IP_PREFIX_GENERIC, schema) || isOfKind(IP_ADDRESS_GENERIC, schema))) {
      return !RELATIONSHIP_VIEW_BLACKLIST.includes(relationship.name);
    }

    const isPeerKindEligibleForForm = relationshipKindForForm.includes(
      relationship.kind as RelationshipKind
    );

    if (isUpdate) return isPeerKindEligibleForForm;

    return isPeerKindEligibleForForm || !relationship.optional;
  });
};
