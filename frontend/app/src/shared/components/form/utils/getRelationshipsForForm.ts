import { relationshipKindForForm } from "@/config/constants";

import {
  IP_ADDRESS_GENERIC,
  IP_PREFIX_GENERIC,
  IP_SUMMARY_RELATIONSHIPS_BLACKLIST,
} from "@/entities/ipam/constants";
import type { RelationshipKind } from "@/entities/nodes/types";
import type { ModelSchema, RelationshipSchema } from "@/entities/schema/types";
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
    if (!isUpdate && relationship.name === "member_of_groups") return true;

    if (schema && (isOfKind(IP_PREFIX_GENERIC, schema) || isOfKind(IP_ADDRESS_GENERIC, schema))) {
      return !IP_SUMMARY_RELATIONSHIPS_BLACKLIST.includes(relationship.name);
    }

    const isPeerKindEligibleForForm = relationshipKindForForm.includes(
      relationship.kind as RelationshipKind
    );

    if (isUpdate) return isPeerKindEligibleForForm;

    return isPeerKindEligibleForForm || !relationship.optional;
  });
};
