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

    // Clearing it in the same write avoids a request for a page window the new row set may not have.
    if (pageKey) setPage(null);
  };

  return [filters, setFilters];
}
