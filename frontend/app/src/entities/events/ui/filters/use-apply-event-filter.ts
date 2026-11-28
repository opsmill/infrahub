import type { Filter } from "@/entities/nodes/filters/domain/model/filter";
import { useFilters } from "@/entities/nodes/filters/ui/hooks/use-filters";

/** Returns a function that sets the `<name>__value` filter, or removes it for a null or undefined value. */
export function useApplyEventFilter(name: string) {
  const [filters, setFilters] = useFilters();

  return (value: Filter["value"]) => {
    const otherFilters = filters.filter((filter) => filter.name !== `${name}__value`);

    if (value === undefined || value === null) {
      setFilters(otherFilters);
      return;
    }

    setFilters([...otherFilters, { name: `${name}__value`, value }]);
  };
}
