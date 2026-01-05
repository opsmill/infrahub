import type { AttributeSchema } from "@/entities/schema/types";

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
    (attribute) => !PREFIX_ATTRIBUTES_EXCLUDED_IN_LIST.includes(attribute.name)
  );
}
