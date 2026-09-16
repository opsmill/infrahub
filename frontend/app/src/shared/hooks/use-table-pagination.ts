import { parseAsInteger, useQueryStates } from "nuqs";
import { useEffect } from "react";

import {
  DEFAULT_PAGE_SIZE,
  getOffset,
  isPageSize,
  type PageSize,
  toPageNumber,
} from "@/shared/utils/table-pagination";

export interface UseTablePaginationOptions {
  urlKey: string;
  defaultPageSize?: PageSize;
}

export interface TablePaginationState {
  page: number;
  pageSize: number;
  offset: number;
  setPage: (page: number) => void;
  setPageSize: (pageSize: number) => void;
  resetPage: () => void;
}

const mountedUrlKeys = new Map<string, number>();

function useUniqueUrlKey(urlKey: string) {
  useEffect(() => {
    if (!import.meta.env.DEV) {
      return;
    }

    const mounted = (mountedUrlKeys.get(urlKey) ?? 0) + 1;
    mountedUrlKeys.set(urlKey, mounted);

    if (mounted > 1) {
      console.warn(
        `useTablePagination: urlKey "${urlKey}" is already used by another mounted table. Give each table its own key, or they will page together.`
      );
    }

    return () => {
      const remaining = (mountedUrlKeys.get(urlKey) ?? 1) - 1;

      if (remaining > 0) {
        mountedUrlKeys.set(urlKey, remaining);
      } else {
        mountedUrlKeys.delete(urlKey);
      }
    };
  }, [urlKey]);
}

export function useTablePagination({
  urlKey,
  defaultPageSize = DEFAULT_PAGE_SIZE,
}: UseTablePaginationOptions): TablePaginationState {
  useUniqueUrlKey(urlKey);

  const [params, setParams] = useQueryStates(
    {
      page: parseAsInteger.withDefault(1),
      pageSize: parseAsInteger.withDefault(defaultPageSize),
    },
    { urlKeys: { page: `${urlKey}_page`, pageSize: `${urlKey}_size` } }
  );

  const page = toPageNumber(params.page);
  const pageSize = isPageSize(params.pageSize) ? params.pageSize : defaultPageSize;

  return {
    page,
    pageSize,
    offset: getOffset(page, pageSize),
    setPage: (nextPage) => {
      setParams({ page: toPageNumber(nextPage) });
    },
    setPageSize: (nextPageSize) => {
      setParams({
        page: 1,
        pageSize: isPageSize(nextPageSize) ? nextPageSize : defaultPageSize,
      });
    },
    resetPage: () => {
      setParams({ page: 1 });
    },
  };
}
