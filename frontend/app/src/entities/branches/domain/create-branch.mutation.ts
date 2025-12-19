import { useMutation } from "@tanstack/react-query";

import { queryClient } from "@/shared/api/rest/client";

import { branchesQueryKeys } from "@/entities/branches/domain/branch.query-keys";
import { createBranch } from "@/entities/branches/domain/create-branch";
import { getBranchesInfiniteQueryOptions } from "@/entities/branches/domain/get-branches.query";

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

      await queryClient.refetchQueries({ queryKey: branchesQueryKeys.all });
    },
  });
}
