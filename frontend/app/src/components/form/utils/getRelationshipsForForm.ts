import { components } from "@/infraops";
import { peersKindForForm } from "@/config/constants";

export const getRelationshipsForForm = (
  relationships: components["schemas"]["RelationshipSchema-Output"][],
  isUpdate?: boolean
) => {
  // Create form includes cardinality many but only if required, edit form doesn't include it at all
  return relationships.filter((relationship) => {
    if (relationship.cardinality === "one") return true;

    const isPeerKindEligibleForForm = peersKindForForm.includes(relationship?.kind ?? "");
    if (isUpdate) return isPeerKindEligibleForForm;

    return isPeerKindEligibleForForm || !relationship.optional;
  });
};
