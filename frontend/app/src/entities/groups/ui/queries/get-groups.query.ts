import { queryOptions, useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";

import { datetimeAtom } from "@/shared/stores/time.atom";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { type GetGroupsParams, getGroups } from "@/entities/groups/domain/get-groups";
import { groupsQueryKeys } from "@/entities/groups/ui/queries/groups.query-keys";

export function getGroupsQueryOptions(params: GetGroupsParams) {
  return queryOptions({
    queryKey: groupsQueryKeys.list(params),
    queryFn: () => getGroups(params),
  });
}

export function useGetGroups({
  objectKind,
  objectId,
}: Omit<GetGroupsParams, "branchName" | "atDate">) {
  const { currentBranch } = useCurrentBranch();
  const timeMachineDate = useAtomValue(datetimeAtom);

  return useQuery(
    getGroupsQueryOptions({
      objectKind,
      objectId,
      branchName: currentBranch.name,
      atDate: timeMachineDate,
    })
  );
}
