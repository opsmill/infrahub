import { FILTER_CONDITION } from "@/entities/nodes/object/ui/filters/filter-condition-select";
import { Filter } from "@/shared/hooks/useFilters";

export function getCurrentFilterCondition(filter?: Filter) {
  if (!filter) return undefined;

  const condition = filter.name.split("__")[1];

  if (condition === "ids") {
    return FILTER_CONDITION.IS_ANY_OF;
  }

  if (condition === "isnull") {
    return filter.value ? FILTER_CONDITION.IS_EMPTY : FILTER_CONDITION.IS_NOT_EMPTY;
  }
}
