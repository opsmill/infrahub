import { parseAsJson, useQueryState } from "nuqs";

import { QSP } from "@/shared/config/qsp";
import { uniqueItemsArray } from "@/shared/utils/array";

import { type Filter, FilterSchema } from "@/entities/nodes/filters/domain/model/filter";

export function useFilters(): [Array<Filter>, (filter: Array<Filter>) => void] {
  const [filters, setFiltersInQueryString] = useQueryState(
    QSP.FILTER,
    parseAsJson(FilterSchema).withDefault([]).withOptions({ history: "push" })
  );

  const setFilters = (newFilters: Filter[]) => {
    // Use unique filters
    const cleanedFilters = uniqueItemsArray(newFilters, "name");

    if (!cleanedFilters || !cleanedFilters?.length) {
      // Set null to remove from QSP
      setFiltersInQueryString(null);
    } else {
      setFiltersInQueryString(cleanedFilters);
    }
  };

  return [filters, setFilters];
}
