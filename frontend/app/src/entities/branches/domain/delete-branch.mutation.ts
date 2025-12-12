import { useMutation } from "@tanstack/react-query";

import { queryClient } from "@/shared/api/rest/client";

import { branchesQueryKeys } from "@/entities/branches/domain/branch.query-keys";
import { deleteBranch } from "@/entities/branches/domain/delete-branch";

export function useDeleteBranchMutation() {
  return useMutation({
    mutationFn: deleteBranch,
    onSuccess: async () => {
      queryClient.invalidateQueries({ queryKey: branchesQueryKeys.all });
    },
  });
}
