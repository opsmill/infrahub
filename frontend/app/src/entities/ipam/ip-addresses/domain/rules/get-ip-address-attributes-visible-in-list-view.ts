import type { AttributeSchema } from "@/entities/schema/domain/model/schema";

const IP_ADDRESS_ATTRIBUTES_EXCLUDED_IN_LIST = ["address"];

export function getIpAddressAttributesVisibleInListView(
  attributes: Array<AttributeSchema>
): Array<AttributeSchema> {
  return attributes.filter(({ name }) => !IP_ADDRESS_ATTRIBUTES_EXCLUDED_IN_LIST.includes(name));
}
