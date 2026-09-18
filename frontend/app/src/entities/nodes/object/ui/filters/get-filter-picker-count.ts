import type { Filter } from "@/entities/nodes/filters/domain/model/filter";
import { isFieldFiltered } from "@/entities/nodes/filters/domain/rules/is-field-filtered";
import type { FilterDefinition } from "@/entities/nodes/object/domain/model/filter-definition";
import { getFilterDefinitionName } from "@/entities/nodes/object/domain/rules/filter-definition";

export function getFilterPickerCount(definitions: FilterDefinition[], filters: Filter[]): number {
  const fieldNames = definitions.map((definition) => getFilterDefinitionName(definition));

  return filters.filter((filter) =>
    fieldNames.some((fieldName) => isFieldFiltered(filter, fieldName))
  ).length;
}
