import { useInfiniteQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";

import type { ContextParams, InfiniteQueryConfig, PaginationParams } from "@/shared/api/types";
import {
  infiniteQueryOptionsWithOptimizedPageSize,
  type OptimizedPageSizeConfig,
} from "@/shared/libs/react-query/infinite-query-options-with-optimized-page-size";
import { datetimeAtom } from "@/shared/stores/time.atom";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { IP_ADDRESS_GENERIC } from "@/entities/ipam/constants";
import {
  type GetIpAddressListParams,
  getIpAddressList,
} from "@/entities/ipam/ip-addresses/domain/get-ip-address-list";
import { hasIncompatibleFiltersForIpAvailability } from "@/entities/ipam/utils";
import { useObjectsCount } from "@/entities/nodes/object/ui/queries/get-objects-count.query";
import { objectQueryKeys } from "@/entities/nodes/object/ui/queries/object.query-keys";

type GetIpAddressListInfiniteQueryParams = Omit<GetIpAddressListParams, keyof PaginationParams>;

export function getIpAddressListInfiniteQueryOptions(
  params: GetIpAddressListInfiniteQueryParams,
  config?: OptimizedPageSizeConfig
) {
  return infiniteQueryOptionsWithOptimizedPageSize(
    {
      queryKey: objectQueryKeys.list({ ...params, objectKind: params.schema.kind! }),
      queryFn: ({ pageParam }) =>
        getIpAddressList({
          ...params,
          offset: pageParam.offset,
          limit: pageParam.limit,
        }),
    },
    config
  );
}

export function useGetIpAddressList(
  params: Omit<GetIpAddressListInfiniteQueryParams, keyof ContextParams>,
  config?: InfiniteQueryConfig<typeof getIpAddressListInfiniteQueryOptions>
) {
  const { currentBranch } = useCurrentBranch();
  const timeMachineDate = useAtomValue(datetimeAtom);

  const {
    data: totalCount,
    isSuccess: isCountSuccess,
    isError: isCountError,
  } = useObjectsCount({
    objectKind:
      params.filters && hasIncompatibleFiltersForIpAvailability(params.filters)
        ? params.schema.kind!
        : IP_ADDRESS_GENERIC,
    filters: params.filters,
  });

  return useInfiniteQuery({
    ...getIpAddressListInfiniteQueryOptions(
      {
        ...params,
        branchName: currentBranch.name,
        atDate: timeMachineDate,
      },
      { totalCount }
    ),
    ...config,
    enabled: (isCountSuccess || isCountError) && config?.enabled,
  });
}
