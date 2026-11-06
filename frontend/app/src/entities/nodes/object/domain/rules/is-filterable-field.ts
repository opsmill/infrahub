import { ATTRIBUTE_KINDS_FOR_LIST_VIEW } from "@/entities/schema/domain/model/attribute-kind";
import type { AttributeKind, FieldSchema } from "@/entities/schema/domain/model/schema";
import { isRelationshipSchema } from "@/entities/schema/domain/rules/is-relationship-schema";

/** Filter definitions only exist for the default list-view kinds, so other columns offer no filter. */
export function isFilterableField(field: FieldSchema): boolean {
  return (
    isRelationshipSchema(field) ||
    ATTRIBUTE_KINDS_FOR_LIST_VIEW.includes(field.kind as AttributeKind)
  );
}
