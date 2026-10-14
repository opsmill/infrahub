import { SEARCH_ANY_FILTER } from "@/entities/nodes/filters/domain/model/filter";
import { useFilters } from "@/entities/nodes/filters/ui/hooks/use-filters";

export const useSearch = (
  filterName: string = SEARCH_ANY_FILTER
): [string, (newSearch: string) => void] => {
  const [filters, setFilters] = useFilters();
  const searchFilter: string | undefined = filters.find((f) => f.name === filterName)?.value;

  const setSearch = (value: string) => {
    setFilters([...filters.filter((f) => f.name !== filterName), { name: filterName, value }]);
  };

  return [searchFilter ?? "", setSearch];
};
