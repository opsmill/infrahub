import { useMutation } from "@tanstack/react-query";

import { queryClient } from "@/shared/api/rest/client";

import { branchesQueryKeys } from "@/entities/branches/domain/branch.query-keys";
import { createBranch } from "@/entities/branches/domain/create-branch";

export function useCreateBranchMutation() {
  return useMutation({
    mutationFn: createBranch,
    onSuccess: async (branchCreated) => {
      if (!branchCreated) return;

      // Wait for refetch to complete before allowing navigation to the new branch
      await queryClient.refetchQueries({ queryKey: branchesQueryKeys.all });
    },
  });
}
