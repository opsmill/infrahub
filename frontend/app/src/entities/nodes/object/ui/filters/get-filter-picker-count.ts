import { isFieldFiltered } from "@/shared/hooks/is-field-filtered";
import type { Filter } from "@/shared/hooks/useFilters";

import { getFilterDefinitionName } from "@/entities/nodes/object/domain/filter-definition";
import { getFilterDefinitions } from "@/entities/nodes/object/ui/filters/get-filter-definitions";
import type { ModelSchema } from "@/entities/schema/types";

export function getFilterPickerCount(schema: ModelSchema, filters: Filter[]): number {
  const fieldNames = getFilterDefinitions(schema).map((definition) =>
    getFilterDefinitionName(definition)
  );

  return filters.filter((filter) =>
    fieldNames.some((fieldName) => isFieldFiltered(filter, fieldName))
  ).length;
}
