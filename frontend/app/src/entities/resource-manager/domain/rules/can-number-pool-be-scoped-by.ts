import { ATTRIBUTE_KIND } from "@/entities/schema/domain/model/attribute-kind";
import type { FieldSchema } from "@/entities/schema/domain/model/schema";
import { isRelationshipSchema } from "@/entities/schema/domain/rules/is-relationship-schema";

const MULTI_VALUE_ATTRIBUTE_KINDS: ReadonlyArray<string> = [
  ATTRIBUTE_KIND.LIST,
  ATTRIBUTE_KIND.JSON,
  ATTRIBUTE_KIND.ANY,
];

export function canNumberPoolBeScopedBy(field: FieldSchema): boolean {
  if (field.optional) return false;

  if (isRelationshipSchema(field)) return field.cardinality === "one";

  return !MULTI_VALUE_ATTRIBUTE_KINDS.includes(field.kind);
}
