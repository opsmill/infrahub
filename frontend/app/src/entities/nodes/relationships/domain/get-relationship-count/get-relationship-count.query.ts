import { queryOptions, useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";

import type { ContextParams, QueryConfig } from "@/shared/api/types";
import { datetimeAtom } from "@/shared/stores/time.atom";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import {
  type GetRelationshipCountParams,
  getRelationshipCount,
} from "@/entities/nodes/relationships/domain/get-relationship-count/get-relationship-count";
import { relationshipsQueryKeys } from "@/entities/nodes/relationships/domain/relationships.query-keys";

export function getRelationshipCountQueryOptions(params: GetRelationshipCountParams) {
  return queryOptions({
    queryKey: relationshipsQueryKeys.count(params),
    queryFn: () => getRelationshipCount(params),
  });
}

export type UseGetRelationshipCountParams = Omit<GetRelationshipCountParams, keyof ContextParams>;
export type UseGetRelationshipCountOptions = QueryConfig<typeof getRelationshipCountQueryOptions>;

export function useGetRelationshipCount(
  params: UseGetRelationshipCountParams,
  config: UseGetRelationshipCountOptions = {}
) {
  const { currentBranch } = useCurrentBranch();
  const timeMachineDate = useAtomValue(datetimeAtom);

  return useQuery({
    ...getRelationshipCountQueryOptions({
      ...params,
      branchName: currentBranch.name,
      atDate: timeMachineDate,
    }),
    ...config,
  });
}
