import { useEffect, useState } from "react";

import { SearchInput, type SearchInputProps } from "@/shared/components/inputs/search-input";
import { SEARCH_ANY_FILTER } from "@/shared/config/constants";
import { useDebounce } from "@/shared/hooks/useDebounce";
import useFilters from "@/shared/hooks/useFilters";
import { useSearch } from "@/shared/hooks/useSearch";

import type { ModelSchema } from "@/entities/schema/types";

interface FilterSearchInputProps extends Omit<SearchInputProps, "onChange" | "value"> {
  schema?: ModelSchema;
}

export const FilterSearchInput = ({ schema, className, ...props }: FilterSearchInputProps) => {
  const [filters, setFilters] = useFilters();
  const [search, setSearch] = useSearch();
  const [prevSearch, setPrevSearch] = useState(search);
  const [inputValue, setInputValue] = useState(search ?? "");
  const debouncedInputValue = useDebounce(inputValue, 300);

  const removeSearchFilter = () => {
    setFilters(filters.filter((f) => f.name !== SEARCH_ANY_FILTER));
  };

  // Update URL when debounced value changes
  useEffect(() => {
    if (debouncedInputValue === search) return;

    if (debouncedInputValue) {
      setSearch(debouncedInputValue);
    } else {
      removeSearchFilter();
    }
  }, [debouncedInputValue]);

  // Sync input when URL changes (ex: browser back/forward)
  if (search !== prevSearch && inputValue === debouncedInputValue) {
    setPrevSearch(search);
    setInputValue(search);
  }
  return (
    <SearchInput
      className="h-8"
      value={inputValue}
      onChange={setInputValue}
      placeholder={"Search " + (schema?.label ?? schema?.name)}
      data-testid="object-list-search-bar"
      onPressReset={removeSearchFilter}
      {...props}
    />
  );
};
