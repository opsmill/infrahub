import { useMutation } from "@tanstack/react-query";
import { useAtomValue } from "jotai";

import { queryClient } from "@/shared/api/rest/client";
import type { ContextParams } from "@/shared/api/types";
import { datetimeAtom } from "@/shared/stores/time.atom";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { type UpdateGroupsParams, updateGroups } from "@/entities/groups/domain/update-groups";
import { objectQueryKeys } from "@/entities/nodes/object/ui/queries/object.query-keys";

export function useUpdateGroups() {
  const { currentBranch } = useCurrentBranch();
  const timeMachineDate = useAtomValue(datetimeAtom);

  return useMutation({
    mutationFn: (params: Omit<UpdateGroupsParams, keyof ContextParams>) =>
      updateGroups({
        ...params,
        branchName: currentBranch.name,
        atDate: timeMachineDate,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: objectQueryKeys.all });
    },
  });
}
