import { useMutation } from "@tanstack/react-query";

import { queryClient } from "@/shared/api/rest/client";

import { branchGitStatusQueryKeys } from "@/entities/branch-git-status/ui/queries/branch-git-status.query-keys";
import { createBranch } from "@/entities/branches/domain/use-cases/create-branch";
import { branchesQueryKeys } from "@/entities/branches/ui/queries/branch.query-keys";
import { getBranchesInfiniteQueryOptions } from "@/entities/branches/ui/queries/get-branches.query";

export function useCreateBranchMutation() {
  return useMutation({
    mutationFn: createBranch,
    onSuccess: async (branchCreated) => {
      if (!branchCreated) return;

      const { queryKey } = getBranchesInfiniteQueryOptions();
      queryClient.setQueryData(queryKey, (oldData) => {
        if (!oldData) return oldData;

        return {
          ...oldData,
          pages: oldData.pages.map((page, index) =>
            index === 0 ? [branchCreated, ...page] : page
          ),
        };
      });

      // Not awaited, so the Git status reads do not keep the create dialog open.
      queryClient.invalidateQueries({ queryKey: branchGitStatusQueryKeys.all });
      await queryClient.refetchQueries({ queryKey: branchesQueryKeys.all });
    },
  });
}
