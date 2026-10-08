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
    // Seeding rather than refetching: the poll then sees the task end even if it finishes before the
    // next poll, and an early refetch that does not list the task yet cannot read as ended.
    onSuccess: async (taskId, { repositoryId }) => {
      const queryKey = repositoriesQueryKeys.runningRefsCheck({ repositoryId });
      // A poll already in flight answered before the task existed; it must not replace the seed.
      await queryClient.cancelQueries({ queryKey });
      queryClient.setQueryData(queryKey, taskId);
    },
  });
}
