import { relationshipKindForForm } from "@/shared/config/constants";

import {
  IP_ADDRESS_GENERIC,
  IP_PREFIX_GENERIC,
  IP_SUMMARY_RELATIONSHIPS_BLACKLIST,
} from "@/entities/ipam/constants";
import type { ModelSchema, RelationshipSchema } from "@/entities/schema/types";
import { isOfKind } from "@/entities/schema/utils/is-of-kind";

export const getRelationshipsForForm = (
  schema: ModelSchema,
  isUpdate?: boolean
): Array<RelationshipSchema> => {
  const isIpamSchema = isOfKind(IP_PREFIX_GENERIC, schema) || isOfKind(IP_ADDRESS_GENERIC, schema);

  return (schema.relationships ?? []).filter((relationship) => {
    if (relationship.cardinality === "one" && relationship.kind !== "Template") return true;
    if (!isUpdate && relationship.name === "member_of_groups") return true;

    if (isIpamSchema) {
      return !IP_SUMMARY_RELATIONSHIPS_BLACKLIST.includes(relationship.name);
    }

    const isEligibleKind = relationshipKindForForm.includes(relationship.kind);

    if (isUpdate) return isEligibleKind;

    return isEligibleKind || !relationship.optional;
  });
};
