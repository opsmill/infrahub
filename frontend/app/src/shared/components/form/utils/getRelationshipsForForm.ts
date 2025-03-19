import { relationshipKindForForm } from "@/config/constants";
import { RelationshipKind } from "@/entities/nodes/types";
import { RelationshipSchema } from "@/entities/schema/types";

export const getRelationshipsForForm = (
  relationships: Array<RelationshipSchema>,
  isUpdate?: boolean
) => {
  // Filter relationships based on cardinality and kind for form inclusion
  // For create forms, include relationships with cardinality 'one', eligible kinds, or mandatory cardinality 'many'
  // For update forms, only include relationships with cardinality 'one' or those with eligible kinds (Attribute or Parent). Other should be display as tabs on details view
  return relationships.filter((relationship) => {
    if (relationship.cardinality === "one" && relationship.kind !== "Template") return true;
    if (!isUpdate && relationship.name === "member_of_groups") return true;

    const isPeerKindEligibleForForm = relationshipKindForForm.includes(
      relationship.kind as RelationshipKind
    );
    if (isUpdate) return isPeerKindEligibleForForm;

    return isPeerKindEligibleForForm || !relationship.optional;
  });
};
