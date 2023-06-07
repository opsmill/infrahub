import { useReactiveVar } from "@apollo/client";
import { StringParam, useQueryParam } from "use-query-params";
import { QSP } from "../config/qsp";
import { comboxBoxFilterVar } from "../graphql/variables/filtersVar";

const useFilters = () => {
  const [filtersInQueryString, setFiltersInQueryString] = useQueryParam(QSP.FILTER, StringParam);
  const currentFilters = useReactiveVar(comboxBoxFilterVar);

  const filters = filtersInQueryString ? JSON.parse(filtersInQueryString) : currentFilters;

  const setFilters = (newFilters?: any) => {
    if (!newFilters || !newFilters?.length) {
      // Set to undefined to remive from QSP
      setFiltersInQueryString(undefined);
    } else {
      // Stringify parameters
      setFiltersInQueryString(JSON.stringify(newFilters));
    }

    // Update reactive var for apollo queries
    comboxBoxFilterVar(newFilters);
  };

  return [filters ?? [], setFilters];
};

export default useFilters;
