import { SEARCH_ANY_FILTER } from "@/shared/config/constants";

import { useFilters } from "@/entities/nodes/filters/ui/hooks/use-filters";

export const useSearch = (): [string, (newSearch: string) => void] => {
  const [filters, setFilters] = useFilters();
  const searchFilter: string | undefined = filters.find((f) => f.name === SEARCH_ANY_FILTER)?.value;

  const setSearch = (value: string) => {
    setFilters([
      ...filters.filter((f) => f.name !== SEARCH_ANY_FILTER),
      { name: SEARCH_ANY_FILTER, value },
    ]);
  };

  return [searchFilter ?? "", setSearch];
};
