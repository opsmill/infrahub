import { ATTRIBUTE_KINDS_FOR_LIST_VIEW } from "@/entities/schema/domain/model/attribute-kind";
import type { AttributeKind, AttributeSchema } from "@/entities/schema/domain/model/schema";

/**
 * `revealedNames` opts specific `display: "extra"` attributes back in without relaxing the kind
 * whitelist: a revealed attribute the list view cannot render stays excluded.
 */
export function getAttributesVisibleInListView(
  attributes: AttributeSchema[],
  revealedNames?: ReadonlySet<string>
): AttributeSchema[] {
  return attributes.filter((attribute) => {
    return (
      (attribute.display !== "extra" || revealedNames?.has(attribute.name) === true) &&
      ATTRIBUTE_KINDS_FOR_LIST_VIEW.includes(attribute.kind as AttributeKind)
    );
  });
}
