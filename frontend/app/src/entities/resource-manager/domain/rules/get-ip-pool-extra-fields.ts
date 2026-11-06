import { isRelationshipVisibleInSummary } from "@/entities/nodes/object/domain/rules/is-relationship-visible-in-summary";
import type {
  AttributeSchema,
  ModelSchema,
  RelationshipSchema,
} from "@/entities/schema/domain/model/schema";

const FIELDS_SHOWN_BY_THE_PAGE = new Set([
  "name",
  "description",
  "ip_namespace",
  "default_prefix_type",
  "default_prefix_length",
  "default_member_type",
  "default_address_type",
]);

export interface IpPoolExtraFields {
  attributes: AttributeSchema[];
  relationships: RelationshipSchema[];
}

export const getIpPoolExtraFields = (schema: ModelSchema): IpPoolExtraFields => ({
  attributes: (schema.attributes ?? []).filter(({ name }) => !FIELDS_SHOWN_BY_THE_PAGE.has(name)),
  relationships: (schema.relationships ?? []).filter(
    (relationship) =>
      relationship.cardinality === "one" &&
      isRelationshipVisibleInSummary(relationship) &&
      !FIELDS_SHOWN_BY_THE_PAGE.has(relationship.name)
  ),
});
