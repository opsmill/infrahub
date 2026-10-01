import { parseAsInteger, parseAsJson, useQueryState } from "nuqs";

import { uniqueItemsArray } from "@/shared/utils/array";

import { type Filter, FilterSchema } from "@/entities/nodes/filters/domain/model/filter";
import {
  SCOPELESS_PAGE_KEY,
  useFilterScope,
} from "@/entities/nodes/filters/ui/filter-scope-context";

export function useFilters(): [Array<Filter>, (filter: Array<Filter>) => void] {
  const { filterKey, pageKey } = useFilterScope();
  const [filters, setFiltersInQueryString] = useQueryState(
    filterKey,
    parseAsJson(FilterSchema).withDefault([]).withOptions({ history: "push" })
  );
  const [, setPage] = useQueryState(pageKey ?? SCOPELESS_PAGE_KEY, parseAsInteger);

  const setFilters = (newFilters: Filter[]) => {
    // Use unique filters
    const cleanedFilters = uniqueItemsArray(newFilters, "name");

    if (!cleanedFilters || !cleanedFilters?.length) {
      // Set null to remove from QSP
      setFiltersInQueryString(null);
    } else {
      setFiltersInQueryString(cleanedFilters);
    }

    // A page number was chosen against the old row set, so it cannot be honoured against the new
    // one. Clearing it here rather than reacting to the change is what keeps the card from spending
    // a request on the old window first.
    if (pageKey) setPage(null);
  };

  return [filters, setFilters];
}
