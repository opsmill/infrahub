import { COMPLEX_ATTRIBUTE_KINDS } from "@/entities/schema/domain/model/attribute-kind";
import type { FieldSchema } from "@/entities/schema/domain/model/schema";
import { isRelationshipSchema } from "@/entities/schema/domain/rules/is-relationship-schema";

export function isFilterableField(field: FieldSchema): boolean {
  return isRelationshipSchema(field) || !COMPLEX_ATTRIBUTE_KINDS.includes(field.kind);
}
