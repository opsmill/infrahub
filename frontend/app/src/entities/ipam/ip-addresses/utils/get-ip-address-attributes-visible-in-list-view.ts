import { AttributeSchema } from "@/entities/schema/types";

const PREFIX_ATTRIBUTES_EXCLUDED_IN_LIST = ["address"];

export function getIpAddressAttributesVisibleInListView(
  attributes: Array<AttributeSchema>
): Array<AttributeSchema> {
  return attributes.filter(({ name }) => !PREFIX_ATTRIBUTES_EXCLUDED_IN_LIST.includes(name));
}
