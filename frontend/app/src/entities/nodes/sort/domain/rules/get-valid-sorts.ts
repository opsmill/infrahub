import {
  NODE_METADATA_SORT_FIELDS,
  type Sort,
  type SortField,
} from "@/entities/nodes/sort/domain/model/sort";
import { isSortableAttribute } from "@/entities/nodes/sort/domain/rules/is-sortable-attribute";
import { isSortableRelationship } from "@/entities/nodes/sort/domain/rules/is-sortable-relationship";
import {
  buildAttributeSortField,
  buildRelationshipSortField,
} from "@/entities/nodes/sort/domain/rules/sort-field";
import type { ModelSchema } from "@/entities/schema/domain/model/schema";
import { getSchema } from "@/entities/schema/domain/use-cases/get-schema";

/**
 * Keeps only sorts targeting one of the schema's sortable fields.
 * Sort fields come straight from the URL, so this allowlist is what keeps
 * arbitrary user input out of GraphQL order arguments.
 */
export function getValidSorts(sorts: Sort[], schema: ModelSchema): Sort[] {
  if (sorts.length === 0) return sorts;

  const attributeFields = (schema.attributes ?? [])
    .filter(isSortableAttribute)
    .map((attribute) => buildAttributeSortField(attribute.name));

  const relationshipFields = (schema.relationships ?? [])
    .filter(isSortableRelationship)
    .flatMap((relationship) => {
      const peerSchema = getSchema(relationship.peer).schema;
      if (!peerSchema) return [];

      return (peerSchema.attributes ?? [])
        .filter(isSortableAttribute)
        .map((attribute) =>
          buildRelationshipSortField(relationship.name, buildAttributeSortField(attribute.name))
        );
    });

  const sortableFields = new Set<SortField>([
    ...attributeFields,
    ...relationshipFields,
    ...NODE_METADATA_SORT_FIELDS.map(({ field }) => field),
  ]);

  return sorts.filter((sort) => sortableFields.has(sort.field));
}
