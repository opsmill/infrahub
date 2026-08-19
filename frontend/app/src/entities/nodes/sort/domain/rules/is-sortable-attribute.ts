import { ATTRIBUTE_KIND } from "@/entities/schema/domain/model/attribute-kind";
import type { AttributeSchema } from "@/entities/schema/domain/model/schema";

/** Kinds whose values have no meaningful (or safe) ordering. */
const NON_SORTABLE_ATTRIBUTE_KINDS: readonly string[] = [
  ATTRIBUTE_KIND.JSON,
  ATTRIBUTE_KIND.LIST,
  ATTRIBUTE_KIND.ANY,
  ATTRIBUTE_KIND.PASSWORD,
  ATTRIBUTE_KIND.HASHED_PASSWORD,
];

export function isSortableAttribute(attribute: AttributeSchema): boolean {
  return !NON_SORTABLE_ATTRIBUTE_KINDS.includes(attribute.kind);
}
