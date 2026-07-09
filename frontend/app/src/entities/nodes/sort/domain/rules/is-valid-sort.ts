import type { Sort } from "@/entities/nodes/sort/domain/model/sort";
import { getSortableFields } from "@/entities/nodes/sort/domain/rules/get-sortable-fields";
import type { ModelSchema } from "@/entities/schema/domain/model/schema";

/**
 * A sort is valid when its field is one of the schema's sortable fields.
 * Sort fields come straight from the URL, so this allowlist is what keeps
 * arbitrary user input out of GraphQL order arguments.
 */
export function isValidSort(sort: Sort, schema: ModelSchema): boolean {
  return getSortableFields(schema).some((sortableField) => sortableField.field === sort.field);
}
