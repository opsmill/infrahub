import { queryOptions, skipToken, useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";

import type { ContextParams, QueryConfig } from "@/shared/api/types";
import { datetimeAtom } from "@/shared/stores/time.atom";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { getNextIpPrefixAvailable } from "@/entities/ipam/ip-prefixes/domain/get-next-ip-prefix-available";

export interface GetNextIpPrefixAvailableQueryOptionsParams extends ContextParams {
  parentPrefixId?: string;
}

export function getNextIpPrefixAvailableQueryOptions({
  branchName,
  atDate,
  parentPrefixId,
}: GetNextIpPrefixAvailableQueryOptionsParams) {
  return queryOptions({
    queryKey: [branchName, atDate, "nextIpPrefixAvailable", parentPrefixId],
    queryFn: parentPrefixId
      ? () => getNextIpPrefixAvailable({ branchName, atDate, parentPrefixId })
      : skipToken,
  });
}

export type UseGetNextIpPrefixAvailableOptions = QueryConfig<
  typeof getNextIpPrefixAvailableQueryOptions
>;

export function useGetNextIpPrefixAvailable(
  params: Omit<GetNextIpPrefixAvailableQueryOptionsParams, keyof ContextParams>,
  config?: UseGetNextIpPrefixAvailableOptions
) {
  const { currentBranch } = useCurrentBranch();
  const atDate = useAtomValue(datetimeAtom);

  return useQuery({
    ...getNextIpPrefixAvailableQueryOptions({
      branchName: currentBranch.name,
      atDate,
      ...params,
    }),
    ...config,
  });
}
