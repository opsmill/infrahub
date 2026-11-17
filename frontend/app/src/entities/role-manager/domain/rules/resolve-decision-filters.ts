import type { Filter } from "@/entities/nodes/filters/domain/model/filter";

const DECISION_VALUE_FILTER = "decision__value";

/** A decision filter can hold an option label, but the API filters on the option's number. */
export function resolveDecisionFilters(
  filters: Filter[],
  options: ReadonlyArray<{ value: number; label: string }>
): Filter[] {
  return filters.map((filter) => {
    if (filter.name === DECISION_VALUE_FILTER) {
      const numericValue = options.find((o) => o.label === filter.value)?.value;
      return { ...filter, value: numericValue ?? filter.value };
    }
    return filter;
  });
}
