import { IP_ADDRESS_GENERIC } from "@/entities/ipam/ip-addresses/domain/model/ip-address";
import { IP_PREFIX_GENERIC } from "@/entities/ipam/ip-prefixes/domain/model/ip-prefix";
import { relationshipKindForForm } from "@/entities/nodes/object/domain/model/view-config";
import type { ModelSchema, RelationshipSchema } from "@/entities/schema/domain/model/schema";
import { isOfKind } from "@/entities/schema/domain/rules/is-of-kind";

// Relationships not editable through IPAM prefix/address forms: group/profile
// memberships are managed elsewhere, children and ip_addresses are derived
const IPAM_FORM_EXCLUDED_RELATIONSHIPS = [
  "member_of_groups",
  "subscriber_of_groups",
  "children",
  "profiles",
  "ip_addresses",
];

export const getRelationshipsForForm = (
  schema: ModelSchema,
  isUpdate?: boolean
): Array<RelationshipSchema> => {
  const isIpamSchema = isOfKind(IP_PREFIX_GENERIC, schema) || isOfKind(IP_ADDRESS_GENERIC, schema);

  return (schema.relationships ?? []).filter((relationship) => {
    if (relationship.cardinality === "one" && relationship.kind !== "Template") return true;
    if (!isUpdate && relationship.name === "member_of_groups") return true;

    if (isIpamSchema) {
      return !IPAM_FORM_EXCLUDED_RELATIONSHIPS.includes(relationship.name);
    }

    const isEligibleKind = relationshipKindForForm.includes(relationship.kind);

    if (isUpdate) return isEligibleKind;

    return isEligibleKind || !relationship.optional;
  });
};
