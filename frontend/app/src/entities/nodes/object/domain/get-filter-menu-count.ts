import type { Filter } from "@/shared/hooks/useFilters";

import { ALL_METADATA_FILTERS } from "@/entities/nodes/object/domain/metadata-filter-definitions";
import type { ModelSchema } from "@/entities/schema/types";

export function getFilterMenuCount(schema: ModelSchema, filters: Filter[]): number {
  const fieldNames = [
    ...(schema.attributes ?? []),
    ...(schema.relationships ?? []),
    ...ALL_METADATA_FILTERS,
  ].map((f) => f.name);

  return filters.filter((filter) =>
    fieldNames.some(
      (fieldName) => filter.name === fieldName || filter.name.startsWith(fieldName + "__")
    )
  ).length;
}
