import type { Sort } from "@/entities/nodes/sort/domain/model/sort";
import { buildAttributeSortField } from "@/entities/nodes/sort/domain/rules/sort-field";
import type { AttributeSchema, RelationshipSchema } from "@/entities/schema/domain/model/schema";

/**
 * The single active sort targeting the given column: returned only when the
 * custom sort holds exactly one entry and its field belongs to the column
 * (attribute: exact attribute sort field; relationship: first `__` token is
 * the relationship name). `null` otherwise — default order, multi-field
 * sorts, or a sort on another column.
 */
export function getColumnActiveSort(
  sorts: Sort[] | null,
  columnSchema: AttributeSchema | RelationshipSchema
): Sort | null {
  const sort = sorts?.length === 1 ? sorts[0] : undefined;
  if (!sort) return null;

  if ("peer" in columnSchema) {
    const [relationshipName] = sort.field.split("__");
    return relationshipName === columnSchema.name ? sort : null;
  }

  return sort.field === buildAttributeSortField(columnSchema.name) ? sort : null;
}
