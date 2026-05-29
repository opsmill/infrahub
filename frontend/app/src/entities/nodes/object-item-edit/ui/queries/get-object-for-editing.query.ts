import { queryOptions, useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";

import type { ContextParams, QueryConfig } from "@/shared/api/types";
import { datetimeAtom } from "@/shared/stores/time.atom";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import {
  type GetObjectForEditingParams,
  getObjectForEditing,
} from "@/entities/nodes/object-item-edit/domain/get-object-for-editing";
import { objectItemEditQueryKeys } from "@/entities/nodes/object-item-edit/ui/queries/object-item-edit.query-keys";

export function getObjectForEditingQueryOptions(params: GetObjectForEditingParams) {
  const { objectKind, objectId, extraRelationshipNames, branchName, atDate } = params;

  return queryOptions({
    queryKey: objectItemEditQueryKeys.detail({
      objectKind,
      objectId,
      extraRelationshipNames,
      branchName,
      atDate,
    }),
    queryFn: () => getObjectForEditing(params),
  });
}

export type UseGetObjectForEditingOptions = QueryConfig<typeof getObjectForEditingQueryOptions>;

export function useGetObjectForEditing(
  params: Omit<GetObjectForEditingParams, keyof ContextParams>,
  config?: UseGetObjectForEditingOptions
) {
  const { currentBranch } = useCurrentBranch();
  const timeMachineDate = useAtomValue(datetimeAtom);

  return useQuery({
    ...getObjectForEditingQueryOptions({
      ...params,
      branchName: currentBranch.name,
      atDate: timeMachineDate,
    }),
    ...config,
  });
}
