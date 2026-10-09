import { parseAsInteger, useQueryStates } from "nuqs";
import { useEffect } from "react";

import { getOffset, PAGE_SIZE, toPageNumber, toPageUrlKey } from "@/shared/utils/table-pagination";

export interface UseTablePaginationOptions {
  urlPrefix: string;
}

export interface TablePaginationState {
  page: number;
  pageSize: number;
  offset: number;
  setPage: (page: number) => void;
}

const mountedUrlPrefixes = new Map<string, number>();

function useUniqueUrlPrefix(urlPrefix: string) {
  useEffect(() => {
    if (!import.meta.env.DEV) {
      return;
    }

    const mountCount = (mountedUrlPrefixes.get(urlPrefix) ?? 0) + 1;

    mountedUrlPrefixes.set(urlPrefix, mountCount);

    if (mountCount > 1) {
      console.warn(
        `useTablePagination: urlPrefix "${urlPrefix}" is already used by another mounted table. Give each table its own key, or they will page together.`
      );
    }

    return () => {
      const remaining = (mountedUrlPrefixes.get(urlPrefix) ?? 1) - 1;

      if (remaining > 0) {
        mountedUrlPrefixes.set(urlPrefix, remaining);
      } else {
        mountedUrlPrefixes.delete(urlPrefix);
      }
    };
  }, [urlPrefix]);
}

export function useTablePagination({ urlPrefix }: UseTablePaginationOptions): TablePaginationState {
  useUniqueUrlPrefix(urlPrefix);

  const [params, setParams] = useQueryStates(
    { page: parseAsInteger.withDefault(1) },
    { urlKeys: { page: toPageUrlKey(urlPrefix) } }
  );

  const page = toPageNumber(params.page);

  return {
    page,
    pageSize: PAGE_SIZE,
    offset: getOffset(page, PAGE_SIZE),
    setPage: (nextPage) => {
      setParams({ page: toPageNumber(nextPage) });
    },
  };
}
