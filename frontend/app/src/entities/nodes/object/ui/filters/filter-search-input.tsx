import { useEffect, useState } from "react";

import { SearchInput, type SearchInputProps } from "@/shared/components/inputs/search-input";
import { useDebounce } from "@/shared/hooks/useDebounce";

import { SEARCH_ANY_FILTER } from "@/entities/nodes/filters/domain/model/filter";
import { useFilters } from "@/entities/nodes/filters/ui/hooks/use-filters";
import { useSearch } from "@/entities/nodes/filters/ui/hooks/use-search";
import type { ModelSchema } from "@/entities/schema/domain/model/schema";

interface FilterSearchInputProps extends Omit<SearchInputProps, "onChange" | "value"> {
  schema?: ModelSchema;
}

export const FilterSearchInput = ({ schema, className, ...props }: FilterSearchInputProps) => {
  const [filters, setFilters] = useFilters();
  const [search, setSearch] = useSearch();
  const [prevSearch, setPrevSearch] = useState(search);
  const [inputValue, setInputValue] = useState(search ?? "");
  const debouncedSearch = useDebounce(inputValue.trim(), 300);

  const removeSearchFilter = () => {
    setFilters(filters.filter((f) => f.name !== SEARCH_ANY_FILTER));
  };

  // Update URL when debounced value changes
  useEffect(() => {
    if (debouncedSearch === search) return;

    if (debouncedSearch) {
      setSearch(debouncedSearch);
    } else {
      removeSearchFilter();
    }
  }, [debouncedSearch]);

  // Sync input when URL changes (ex: browser back/forward)
  if (search !== prevSearch && inputValue.trim() === debouncedSearch) {
    setPrevSearch(search);
    // Rewriting an input that trims to the search would drop a space typed between two words.
    if (inputValue.trim() !== search) setInputValue(search);
  }
  return (
    <SearchInput
      className="h-8 max-w-xs rounded-xl"
      value={inputValue}
      onChange={setInputValue}
      placeholder={"Search " + (schema?.label ?? schema?.name)}
      data-testid="object-list-search-bar"
      onPressReset={removeSearchFilter}
      {...props}
    />
  );
};
