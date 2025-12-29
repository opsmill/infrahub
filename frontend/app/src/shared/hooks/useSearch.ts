import { SEARCH_ANY_FILTER } from "@/shared/config/constants";

import useFilters from "./useFilters";

export type Filter = {
  name: `${string}__${string}`;
  value: any;
  display_label?: string;
};

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
