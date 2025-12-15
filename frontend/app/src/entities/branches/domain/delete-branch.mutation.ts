import { useMutation } from "@tanstack/react-query";

import { queryClient } from "@/shared/api/rest/client";

import { deleteBranch } from "@/entities/branches/domain/delete-branch";
import { getBranchesQueryOptions } from "@/entities/branches/domain/get-branches.query";

export function useDeleteBranchMutation() {
  return useMutation({
    mutationFn: deleteBranch,
    onSuccess: async (branchDeleted) => {
      if (!branchDeleted) return;

      const { queryKey } = getBranchesQueryOptions();
      queryClient.setQueryData(queryKey, (oldBranches) =>
        oldBranches?.filter((branch) => branch.name !== branchDeleted)
      );
      queryClient.invalidateQueries({ queryKey });
    },
  });
}
