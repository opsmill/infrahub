import { parseAsJson, useQueryState } from "nuqs";
import * as z from "zod";

import { QSP } from "@/shared/config/qsp";
import { uniqueItemsArray } from "@/shared/utils/array";

import { AVAILABLE_IP_FILTER_NAME } from "@/entities/ipam/constants";

export const FilterSchema = z.array(
  z.object({
    name: z.union([
      z.string().regex(/^.+__.+$/), // Allows any string with at least one "__" separator
      z.literal(AVAILABLE_IP_FILTER_NAME),
      z.literal("order"),
    ]),
    value: z.any(),
  })
);

export type Filter = z.infer<typeof FilterSchema>[number];

const useFilters = (): [Array<Filter>, (filter: Array<Filter>) => void] => {
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
};

export default useFilters;
