import { queryOptions, skipToken, useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";

import type { ContextParams, QueryConfig } from "@/shared/api/types";
import { datetimeAtom } from "@/shared/stores/time.atom";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";

import { getNextIpAddressAvailable } from "./get-next-ip-address-available";

export interface GetNextIpAddressAvailableQueryOptionsParams extends ContextParams {
  parentPrefixId?: string;
}

export function getNextIpAddressAvailableQueryOptions({
  branchName,
  atDate,
  parentPrefixId,
}: GetNextIpAddressAvailableQueryOptionsParams) {
  return queryOptions({
    queryKey: [branchName, atDate, "nextIpAddressAvailable", parentPrefixId],
    queryFn: parentPrefixId
      ? () => getNextIpAddressAvailable({ branchName, atDate, parentPrefixId })
      : skipToken,
  });
}

export type UseGetNextIpAddressAvailableOptions = QueryConfig<
  typeof getNextIpAddressAvailableQueryOptions
>;

export function useGetNextIpAddressAvailable(
  params: Omit<GetNextIpAddressAvailableQueryOptionsParams, keyof ContextParams>,
  config?: UseGetNextIpAddressAvailableOptions
) {
  const { currentBranch } = useCurrentBranch();
  const atDate = useAtomValue(datetimeAtom);

  return useQuery({
    ...getNextIpAddressAvailableQueryOptions({
      branchName: currentBranch.name,
      atDate,
      ...params,
    }),
    ...config,
  });
}
