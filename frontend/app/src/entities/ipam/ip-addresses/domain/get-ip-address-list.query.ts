import { infiniteQueryOptions, useInfiniteQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";

import type { ContextParams, PaginationParams } from "@/shared/api/types";
import { datetimeAtom } from "@/shared/stores/time.atom";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import {
  type GetIpAddressListParams,
  getIpAddressList,
} from "@/entities/ipam/ip-addresses/domain/get-ip-address-list";
import { OBJECTS_PER_PAGE } from "@/entities/nodes/object/domain/get-objects";
import { objectQueryKeys } from "@/entities/nodes/object/domain/object.query-keys";

type GetIpAddressListInfiniteQueryParams = Omit<GetIpAddressListParams, keyof PaginationParams>;

export function getIpAddressListInfiniteQueryOptions(params: GetIpAddressListInfiniteQueryParams) {
  return infiniteQueryOptions({
    queryKey: objectQueryKeys.list({ ...params, objectKind: params.schema.kind! }),
    queryFn: ({ pageParam }) => {
      return getIpAddressList({
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

export function useGetIpAddressList(
  params: Omit<GetIpAddressListInfiniteQueryParams, keyof ContextParams>
) {
  const { currentBranch } = useCurrentBranch();
  const timeMachineDate = useAtomValue(datetimeAtom);

  return useInfiniteQuery(
    getIpAddressListInfiniteQueryOptions({
      ...params,
      branchName: currentBranch.name,
      atDate: timeMachineDate,
    })
  );
}
