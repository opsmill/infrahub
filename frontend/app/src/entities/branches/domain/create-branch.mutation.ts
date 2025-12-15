import { useMutation } from "@tanstack/react-query";

import { queryClient } from "@/shared/api/rest/client";

import { createBranch } from "@/entities/branches/domain/create-branch";
import { getBranchesQueryOptions } from "@/entities/branches/domain/get-branches.query";

export function useCreateBranchMutation() {
  return useMutation({
    mutationFn: createBranch,

    onSuccess: async (branchCreated) => {
      if (!branchCreated) return;

      const { queryKey } = getBranchesQueryOptions();
      queryClient.setQueryData(queryKey, (oldBranches) => [...(oldBranches ?? []), branchCreated]);
      queryClient.invalidateQueries({ queryKey });
    },
  });
}
