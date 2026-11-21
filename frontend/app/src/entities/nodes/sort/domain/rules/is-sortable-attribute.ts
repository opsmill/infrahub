import { COMPLEX_ATTRIBUTE_KINDS } from "@/entities/schema/domain/model/attribute-kind";
import type { AttributeSchema } from "@/entities/schema/domain/model/schema";

export function isSortableAttribute(attribute: AttributeSchema): boolean {
  return !COMPLEX_ATTRIBUTE_KINDS.includes(attribute.kind);
}
