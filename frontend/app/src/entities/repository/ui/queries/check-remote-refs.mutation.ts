import { useMutation, useQueryClient } from "@tanstack/react-query";

import type { BranchContextParams } from "@/shared/api/types";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import {
  type CheckRemoteRefsParams,
  checkRemoteRefs,
} from "@/entities/repository/domain/use-cases/check-remote-refs";
import { repositoriesQueryKeys } from "@/entities/repository/ui/queries/repository.query-keys";

export function useCheckRemoteRefsMutation() {
  const queryClient = useQueryClient();
  const { currentBranch } = useCurrentBranch();

  return useMutation({
    mutationFn: (params: Omit<CheckRemoteRefsParams, keyof BranchContextParams>) => {
      return checkRemoteRefs({ branchName: currentBranch.name, ...params });
    },
    // Seeding the started task means the poll sees it end even if it finishes before the next poll,
    // which is when the poll refetches the commit log.
    onSuccess: (taskId, { repositoryId }) => {
      const queryKey = repositoriesQueryKeys.runningRefsCheck({ repositoryId });
      queryClient.setQueryData(queryKey, taskId);
      return queryClient.invalidateQueries({ queryKey });
    },
  });
}
