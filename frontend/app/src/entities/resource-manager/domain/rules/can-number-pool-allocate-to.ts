import { ATTRIBUTE_KIND } from "@/entities/schema/domain/model/attribute-kind";
import type { AttributeSchema } from "@/entities/schema/domain/model/schema";

export function canNumberPoolAllocateTo(attribute: AttributeSchema): boolean {
  return attribute.kind === ATTRIBUTE_KIND.NUMBER && !attribute.read_only;
}
