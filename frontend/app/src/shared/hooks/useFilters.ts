import { QSP } from "@/config/qsp";
import { AVAILABLE_IP_FILTER_NAME } from "@/entities/ipam/constants";
import { uniqueItemsArray } from "@/shared/utils/array";
import { StringParam, useQueryParam } from "use-query-params";

export type Filter = {
  name: `${string}__${string}` | typeof AVAILABLE_IP_FILTER_NAME | "order";
  value: any;
  display_label?: string;
};

const useFilters = (): [Array<Filter>, (filter: Array<Filter>) => void] => {
  const [filtersInQueryString, setFiltersInQueryString] = useQueryParam(QSP.FILTER, StringParam);

  const filters = filtersInQueryString ? JSON.parse(filtersInQueryString) : [];

  const setFilters = (newFilters: Filter[]) => {
    // Use unique filters
    const cleanedFilters = uniqueItemsArray(newFilters, "name");

    if (!cleanedFilters || !cleanedFilters?.length) {
      // Set to undefined to remive from QSP
      setFiltersInQueryString(undefined);
    } else {
      // Stringify parameters
      setFiltersInQueryString(JSON.stringify(cleanedFilters));
    }
  };

  return [filters ?? [], setFilters];
};

export default useFilters;
