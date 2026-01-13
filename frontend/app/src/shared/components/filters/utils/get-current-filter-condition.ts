import type { Filter } from "@/shared/hooks/useFilters";

import {
  FILTER_CONDITION,
  type FilterCondition,
} from "@/entities/nodes/object/ui/filters/filter-condition-select";

/**
 * Determines the current filter condition based on the filter name and value.
 *
 * @param filter - The filter object to analyze
 * @returns The corresponding filter condition or undefined if no filter is provided
 */
export function getCurrentFilterCondition(filter?: Filter): FilterCondition | undefined {
  if (!filter) return;

  const parts = filter.name.split("__");
  const condition = parts.length > 1 ? parts[parts.length - 1] : "";

  switch (condition) {
    case "value":
      return FILTER_CONDITION.CONTAINS;
    case "ids":
    case "values":
      return FILTER_CONDITION.IS_ANY_OF;
    case "isnull":
      return filter.value ? FILTER_CONDITION.IS_EMPTY : FILTER_CONDITION.IS_NOT_EMPTY;
    default:
      return;
  }
}
