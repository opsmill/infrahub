import type { SortField } from "@/entities/nodes/sort/domain/model/sort";

/** Sort field path for an attribute, e.g. `name__value`. */
export function buildAttributeSortField(attributeName: string): SortField {
  return `${attributeName}__value`;
}

/** Sort field path for a peer field reached through a relationship, e.g. `site__name__value`. */
export function buildRelationshipSortField(
  relationshipName: string,
  attributeField: SortField
): SortField {
  return `${relationshipName}__${attributeField}`;
}

/** Inverse of `buildRelationshipSortField`'s prefix: the field's first `__` token names the relationship. */
export function sortFieldBelongsToRelationship(
  field: SortField,
  relationshipName: string
): boolean {
  const [firstToken] = field.split("__");
  return firstToken === relationshipName;
}
