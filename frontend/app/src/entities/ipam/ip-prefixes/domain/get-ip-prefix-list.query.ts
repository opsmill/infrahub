import { infiniteQueryOptions, useInfiniteQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";

import type { ContextParams, PaginationParams } from "@/shared/api/types";
import { datetimeAtom } from "@/shared/stores/time.atom";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import {
  type GetIpPrefixListParams,
  getIpPrefixList,
} from "@/entities/ipam/ip-prefixes/domain/get-ip-prefix-list";
import { OBJECTS_PER_PAGE } from "@/entities/nodes/object/domain/get-objects";
import { objectQueryKeys } from "@/entities/nodes/object/domain/object.query-keys";

type GetIpPrefixListInfiniteQueryParams = Omit<GetIpPrefixListParams, keyof PaginationParams>;

export function getIpPrefixListInfiniteQueryOptions(params: GetIpPrefixListInfiniteQueryParams) {
  return infiniteQueryOptions({
    queryKey: objectQueryKeys.list({ ...params, objectKind: params.schema.kind! }),
    queryFn: ({ pageParam }) => {
      return getIpPrefixList({
        ...params,
        offset: pageParam,
      });
    },
    initialPageParam: 0,
    getNextPageParam: (lastPage, _, lastPageParam) => {
      if (lastPage.length < OBJECTS_PER_PAGE) {
        return;
      }
      return lastPageParam + OBJECTS_PER_PAGE;
    },
  });
}

export function useGetIpPrefixList(
  params: Omit<GetIpPrefixListInfiniteQueryParams, keyof ContextParams>
) {
  const { currentBranch } = useCurrentBranch();
  const timeMachineDate = useAtomValue(datetimeAtom);

  return useInfiniteQuery(
    getIpPrefixListInfiniteQueryOptions({
      ...params,
      branchName: currentBranch.name,
      atDate: timeMachineDate,
    })
  );
}
