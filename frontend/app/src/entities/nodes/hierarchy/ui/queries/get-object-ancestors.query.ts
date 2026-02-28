import { queryOptions, useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";

import type { ContextParams, QueryConfig } from "@/shared/api/types";
import { datetimeAtom } from "@/shared/stores/time.atom";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import {
  type GetObjectAncestorsParams,
  getObjectAncestors,
} from "@/entities/nodes/hierarchy/domain/get-object-ancestors";
import { objectQueryKeys } from "@/entities/nodes/object/ui/queries/object.query-keys";

export function getObjectAncestorsQueryOptions(params: GetObjectAncestorsParams) {
  return queryOptions({
    queryKey: objectQueryKeys.ancestors(params),
    queryFn: () => getObjectAncestors(params),
  });
}

export type UseGetObjectAncestorsQueryConfig = QueryConfig<typeof getObjectAncestorsQueryOptions>;

export function useGetObjectAncestors(
  params: Omit<GetObjectAncestorsParams, keyof ContextParams>,
  config?: UseGetObjectAncestorsQueryConfig
) {
  const { currentBranch } = useCurrentBranch();
  const timeMachineDate = useAtomValue(datetimeAtom);

  return useQuery({
    ...getObjectAncestorsQueryOptions({
      branchName: currentBranch.name,
      atDate: timeMachineDate,
      ...params,
    }),
    ...config,
  });
}
