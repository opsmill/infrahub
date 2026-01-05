import type { AttributeKind, AttributeSchema } from "@/entities/schema/types";

import { ATTRIBUTE_KINDS_FOR_LIST_VIEW } from "../../../schema/constants";

export function getAttributesVisibleInListView(attributes: AttributeSchema[]): AttributeSchema[] {
  return attributes.filter((attribute) => {
    return ATTRIBUTE_KINDS_FOR_LIST_VIEW.includes(attribute.kind as AttributeKind);
  });
}
