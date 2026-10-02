import React from "react";

import { QSP } from "@/shared/config/qsp";
import { getPageUrlKey } from "@/shared/utils/table-pagination";

export interface FilterScope {
  filterKey: string;
  sortKey: string;
  /** The page key to clear when the filters or the order change; absent for the global scope. */
  pageKey: string | null;
}

/** Read but never written: the global scope has no page of its own to clear. */
export const SCOPELESS_PAGE_KEY = "_unscoped_page";

const GLOBAL_FILTER_SCOPE: FilterScope = {
  filterKey: QSP.FILTER,
  sortKey: QSP.SORT,
  pageKey: null,
};

const FilterScopeContext = React.createContext<FilterScope | null>(null);

export interface FilterScopeProviderProps {
  urlKey: string;
  children?: React.ReactNode;
}

/**
 * Gives one surface its own filter, order and page url keys.
 *
 * A surface that shares the global keys reads filters set by any other table and has its own
 * overwritten in turn, and it cannot tell its own changes from theirs. Scoping is what lets a
 * surface narrow the conditions it offers and trust that nothing it cannot honour arrives.
 */
export function FilterScopeProvider({ urlKey, children }: FilterScopeProviderProps) {
  const scope: FilterScope = {
    filterKey: `${urlKey}_${QSP.FILTER}`,
    sortKey: `${urlKey}_${QSP.SORT}`,
    pageKey: getPageUrlKey(urlKey),
  };

  return <FilterScopeContext value={scope}>{children}</FilterScopeContext>;
}

/**
 * The filter scope of the surface this component sits in.
 *
 * Non-throwing: most of the product filters against the global keys, and that is the right reading
 * of "no surface said otherwise".
 */
export function useFilterScope(): FilterScope {
  return React.use(FilterScopeContext) ?? GLOBAL_FILTER_SCOPE;
}
