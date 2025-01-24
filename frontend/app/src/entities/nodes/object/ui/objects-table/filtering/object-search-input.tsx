import { SEARCH_ANY_FILTER } from "@/config/constants";
import { IModelSchema } from "@/entities/schema/stores/schema.atom";
import { SearchInput, SearchInputProps } from "@/shared/components/inputs/search-input";
import useFilters, { type Filter } from "@/shared/hooks/useFilters";
import { debounce } from "@/shared/utils/common";

interface ObjectSearchInputProps extends Omit<SearchInputProps, "onChange"> {
  schema: IModelSchema;
}

export const ObjectSearchInput = ({ schema, className, ...props }: ObjectSearchInputProps) => {
  const [filters, setFilters] = useFilters();

  const handleSearch = (text: string) => {
    const newFilters = text
      ? [
          ...filters.filter((f) => f.name !== SEARCH_ANY_FILTER),
          { name: SEARCH_ANY_FILTER, value: text } as Filter,
        ]
      : filters.filter((f) => f.name !== SEARCH_ANY_FILTER);

    setFilters(newFilters);
  };

  const search = filters.find((filter) => filter.name === SEARCH_ANY_FILTER)?.value;
  const debouncedHandleSearch = debounce(handleSearch, 500);

  return (
    <SearchInput
      className="h-8 border-none"
      defaultValue={search}
      onChange={debouncedHandleSearch}
      placeholder={"Search " + (schema.label ?? schema.name)}
      data-testid="object-list-search-bar"
      {...props}
    />
  );
};
