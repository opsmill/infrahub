import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import {
  GetIpPrefixListParams,
  getIpPrefixList,
} from "@/entities/ipam/prefixes/domain/get-ip-prefix-list";
import { OBJECTS_PER_PAGE } from "@/entities/nodes/object/domain/get-objects";
import { ContextParams, PaginationParams } from "@/shared/api/types";
import { datetimeAtom } from "@/shared/stores/time.atom";
import { infiniteQueryOptions, useInfiniteQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";

type GetIpPrefixListInfiniteQueryParams = Omit<GetIpPrefixListParams, keyof PaginationParams>;

export function getIpPrefixListInfiniteQueryOptions({
  schema,
  filters,
  branchName,
  atDate,
}: GetIpPrefixListInfiniteQueryParams) {
  return infiniteQueryOptions({
    queryKey: [branchName, atDate, "objects", schema.kind, filters],
    queryFn: ({ pageParam }) => {
      return getIpPrefixList({
        schema,
        filters,
        offset: pageParam,
        branchName,
        atDate,
      });
    },
    initialPageParam: 0,
    getNextPageParam: (lastPage, _, lastPageParam) => {
      if (lastPage.length < OBJECTS_PER_PAGE) {
        return undefined;
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
