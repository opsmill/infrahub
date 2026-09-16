import { parseAsInteger, useQueryStates } from "nuqs";
import { useEffect } from "react";

import { getOffset, PAGE_SIZE, toPageNumber } from "@/shared/utils/table-pagination";

export interface UseTablePaginationOptions {
  urlKey: string;
}

export interface TablePaginationState {
  page: number;
  pageSize: number;
  offset: number;
  setPage: (page: number) => void;
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

export function useTablePagination({ urlKey }: UseTablePaginationOptions): TablePaginationState {
  useUniqueUrlKey(urlKey);

  const [params, setParams] = useQueryStates(
    { page: parseAsInteger.withDefault(1) },
    { urlKeys: { page: `${urlKey}_page` } }
  );

  const page = toPageNumber(params.page);

  return {
    page,
    pageSize: PAGE_SIZE,
    offset: getOffset(page, PAGE_SIZE),
    setPage: (nextPage) => {
      setParams({ page: toPageNumber(nextPage) });
    },
    resetPage: () => {
      setParams({ page: 1 });
    },
  };
}
