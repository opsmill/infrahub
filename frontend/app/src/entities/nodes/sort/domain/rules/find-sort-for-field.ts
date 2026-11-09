import type { Sort } from "@/entities/nodes/sort/domain/model/sort";
import { buildAttributeSortField } from "@/entities/nodes/sort/domain/rules/sort-field";
import type { AttributeSchema, RelationshipSchema } from "@/entities/schema/domain/model/schema";
import { isRelationshipSchema } from "@/entities/schema/domain/rules/is-relationship-schema";

/**
 * The single active sort targeting the given schema field: returned only when
 * the sorts hold exactly one entry belonging to that field (attribute: exact
 * attribute sort field; relationship: first `__` token is the relationship
 * name). `null` otherwise — default order, multi-field sorts, or a sort on
 * another field.
 */
export function findSortForField(
  sorts: Sort[] | null,
  fieldSchema: AttributeSchema | RelationshipSchema
): Sort | null {
  const sort = sorts?.length === 1 ? sorts[0] : undefined;
  if (!sort) return null;

  if (isRelationshipSchema(fieldSchema)) {
    const [relationshipName] = sort.field.split("__");
    return relationshipName === fieldSchema.name ? sort : null;
  }

  return sort.field === buildAttributeSortField(fieldSchema.name) ? sort : null;
}
