import { queryOptions, useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";

import type { ContextParams } from "@/shared/api/types";
import { datetimeAtom } from "@/shared/stores/time.atom";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { objectQueryKeys } from "@/entities/nodes/object/ui/queries/object.query-keys";

import { type GetObjectsCountParams, getObjectsCount } from "../../domain/get-objects-count";

export function getObjectsCountQueryOptions(params: GetObjectsCountParams) {
  return queryOptions({
    queryKey: objectQueryKeys.count(params),
    queryFn: async () => {
      return getObjectsCount(params);
    },
  });
}

export function useObjectsCount(params: Omit<GetObjectsCountParams, keyof ContextParams>) {
  const { currentBranch } = useCurrentBranch();
  const timeMachineDate = useAtomValue(datetimeAtom);

  return useQuery(
    getObjectsCountQueryOptions({
      ...params,
      branchName: currentBranch.name,
      atDate: timeMachineDate,
    })
  );
}
