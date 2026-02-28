import { useMutation } from "@tanstack/react-query";
import { useAtomValue } from "jotai";

import { queryClient } from "@/shared/api/rest/client";
import { datetimeAtom } from "@/shared/stores/time.atom";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { type UpdateGroupsParams, updateGroups } from "@/entities/groups/domain/update-groups";
import { groupsQueryKeys } from "@/entities/groups/ui/queries/groups.query-keys";

export function useUpdateGroups() {
  const { currentBranch } = useCurrentBranch();
  const timeMachineDate = useAtomValue(datetimeAtom);

  return useMutation({
    mutationFn: (params: Omit<UpdateGroupsParams, "branchName" | "atDate">) =>
      updateGroups({
        ...params,
        branchName: currentBranch.name,
        atDate: timeMachineDate,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: groupsQueryKeys.all });
    },
  });
}
