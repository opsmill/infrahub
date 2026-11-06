import {
  ATTRIBUTE_KINDS_FOR_LIST_VIEW,
  ATTRIBUTE_KINDS_REVEALABLE_IN_LIST_VIEW,
} from "@/entities/schema/domain/model/attribute-kind";
import type { AttributeKind, AttributeSchema } from "@/entities/schema/domain/model/schema";

/**
 * A revealed attribute skips the `display: "extra"` gate and may use a kind that is never a
 * default column.
 */
export function getAttributesVisibleInListView(
  attributes: AttributeSchema[],
  revealedNames: ReadonlySet<string> = new Set()
): AttributeSchema[] {
  return attributes.filter((attribute) => {
    const kind = attribute.kind as AttributeKind;

    if (revealedNames.has(attribute.name)) {
      return ATTRIBUTE_KINDS_REVEALABLE_IN_LIST_VIEW.includes(kind);
    }

    return attribute.display !== "extra" && ATTRIBUTE_KINDS_FOR_LIST_VIEW.includes(kind);
  });
}
