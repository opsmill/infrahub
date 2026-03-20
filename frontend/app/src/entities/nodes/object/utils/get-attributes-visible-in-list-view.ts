import { ATTRIBUTE_KINDS_FOR_LIST_VIEW } from "@/entities/schema/constants";
import type { AttributeKind, AttributeSchema } from "@/entities/schema/types";

export function getAttributesVisibleInListView(attributes: AttributeSchema[]): AttributeSchema[] {
  return attributes.filter((attribute) => {
    return ATTRIBUTE_KINDS_FOR_LIST_VIEW.includes(attribute.kind as AttributeKind);
  });
}
