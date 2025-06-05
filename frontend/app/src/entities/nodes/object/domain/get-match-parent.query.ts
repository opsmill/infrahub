import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import {
  GetMatchParentParams,
  getMatchParent,
} from "@/entities/nodes/object/domain/get-match-parent";
import { ContextParams } from "@/shared/api/types";
import { datetimeAtom } from "@/shared/stores/time.atom";
import { queryOptions, useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";

export function getMatchParentQueryOptions(params: GetMatchParentParams) {
  return queryOptions({
    queryKey: [params.branchName, params.atDate, "objects", params.objectId],
    queryFn: () => getMatchParent(params),
  });
}

export function useGetMatchParent(params: Omit<GetMatchParentParams, keyof ContextParams>) {
  const { currentBranch } = useCurrentBranch();
  const timeMachineDate = useAtomValue(datetimeAtom);

  return useQuery(
    getMatchParentQueryOptions({
      ...params,
      branchName: currentBranch.name,
      atDate: timeMachineDate,
    })
  );
}
