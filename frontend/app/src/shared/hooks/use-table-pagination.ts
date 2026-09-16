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
}

const mountedUrlKeys = new Map<string, Set<WeakRef<object>>>();

function useUniqueUrlKey(urlKey: string) {
  useEffect(() => {
    if (!import.meta.env.DEV) {
      return;
    }

    const holders = mountedUrlKeys.get(urlKey) ?? new Set<WeakRef<object>>();

    for (const holder of holders) {
      if (holder.deref() === undefined) {
        holders.delete(holder);
      }
    }

    // The cleanup stands in for the mounted table and is held only weakly, so a cleanup React never
    // ran is collected instead of leaving the key looking occupied for the rest of the session.
    const release = () => {
      holders.delete(releaseRef);

      if (holders.size === 0) {
        mountedUrlKeys.delete(urlKey);
      }
    };
    const releaseRef = new WeakRef(release);

    holders.add(releaseRef);
    mountedUrlKeys.set(urlKey, holders);

    if (holders.size > 1) {
      console.warn(
        `useTablePagination: urlKey "${urlKey}" is already used by another mounted table. Give each table its own key, or they will page together.`
      );
    }

    return release;
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
  };
}
