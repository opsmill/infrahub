import type { Filter } from "@/entities/nodes/filters/domain/model/filter";
import { isFieldFiltered } from "@/entities/nodes/filters/domain/rules/is-field-filtered";
import { getFilterDefinitionName } from "@/entities/nodes/object/domain/rules/filter-definition";
import { getFilterDefinitions } from "@/entities/nodes/object/ui/filters/get-filter-definitions";
import type { ModelSchema } from "@/entities/schema/domain/model/schema";

export function getFilterPickerCount(schema: ModelSchema, filters: Filter[]): number {
  const fieldNames = getFilterDefinitions(schema).map((definition) =>
    getFilterDefinitionName(definition)
  );

  return filters.filter((filter) =>
    fieldNames.some((fieldName) => isFieldFiltered(filter, fieldName))
  ).length;
}
