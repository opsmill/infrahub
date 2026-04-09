import { isFieldFiltered } from "@/shared/hooks/is-field-filtered";
import type { Filter } from "@/shared/hooks/useFilters";

import { ALL_METADATA_FILTERS } from "@/entities/nodes/object/domain/metadata-filter-definitions";
import type { ModelSchema } from "@/entities/schema/types";

export function getFilterPickerCount(schema: ModelSchema, filters: Filter[]): number {
  const fieldNames = [
    ...(schema.attributes ?? []),
    ...(schema.relationships ?? []),
    ...ALL_METADATA_FILTERS,
  ].map((f) => f.name);

  return filters.filter((filter) =>
    fieldNames.some((fieldName) => isFieldFiltered(filter, fieldName))
  ).length;
}
