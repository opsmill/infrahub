import { queryOptions, useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";

import type { ContextParams, QueryConfig } from "@/shared/api/types";
import { datetimeAtom } from "@/shared/stores/time.atom";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { type GetObjectParams, getObject } from "@/entities/nodes/object/domain/get-object";
import { objectQueryKeys } from "@/entities/nodes/object/ui/queries/object.query-keys";

export function getObjectQueryOptions(params: GetObjectParams) {
  return queryOptions({
    queryKey: objectQueryKeys.detail({ ...params, objectKind: params.objectSchema.kind! }),
    queryFn: () => getObject(params),
  });
}

export function useGetObject(
  params: Omit<GetObjectParams, keyof ContextParams>,
  config?: QueryConfig<typeof getObjectQueryOptions>
) {
  const { currentBranch } = useCurrentBranch();
  const timeMachineDate = useAtomValue(datetimeAtom);

  return useQuery({
    ...getObjectQueryOptions({
      ...params,
      branchName: currentBranch.name,
      atDate: timeMachineDate,
    }),
    ...config,
  });
}
