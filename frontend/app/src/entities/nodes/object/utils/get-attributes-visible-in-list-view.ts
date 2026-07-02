import { ATTRIBUTE_KINDS_FOR_LIST_VIEW } from "@/entities/schema/domain/model/attribute-kind";
import type { AttributeKind, AttributeSchema } from "@/entities/schema/domain/model/types";

export function getAttributesVisibleInListView(attributes: AttributeSchema[]): AttributeSchema[] {
  return attributes.filter((attribute) => {
    return (
      attribute.display !== "extra" &&
      ATTRIBUTE_KINDS_FOR_LIST_VIEW.includes(attribute.kind as AttributeKind)
    );
  });
}
