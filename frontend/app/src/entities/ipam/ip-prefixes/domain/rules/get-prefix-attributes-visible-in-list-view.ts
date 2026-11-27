import { COMPLEX_ATTRIBUTE_KINDS } from "@/entities/schema/domain/model/attribute-kind";
import type { AttributeSchema } from "@/entities/schema/domain/model/schema";

const PREFIX_ATTRIBUTES_EXCLUDED_IN_LIST = [
  "prefix",
  "network_address",
  "hostmask",
  "is_top_level",
  "netmask",
  "broadcast_address",
];

export function getPrefixAttributesVisibleInListView(
  attributes: Array<AttributeSchema>
): Array<AttributeSchema> {
  return attributes.filter(
    (attribute) =>
      !PREFIX_ATTRIBUTES_EXCLUDED_IN_LIST.includes(attribute.name) &&
      !COMPLEX_ATTRIBUTE_KINDS.includes(attribute.kind)
  );
}
