import type { AttributeSchema } from "@/entities/schema/domain/model/schema";

// All attributes are visible by default on detailed view
export function getAttributesVisibleInDetailedView(
  attributes: AttributeSchema[]
): AttributeSchema[] {
  return attributes;
}
