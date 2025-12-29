import { useMutation } from "@tanstack/react-query";

import { queryClient } from "@/shared/api/rest/client";

import { deleteBranch } from "@/entities/branches/domain/delete-branch";
import { getBranchesInfiniteQueryOptions } from "@/entities/branches/domain/get-branches.query";

export function useDeleteBranchMutation() {
  return useMutation({
    mutationFn: deleteBranch,
    onSuccess: async (branchDeleted) => {
      if (!branchDeleted) return;

      const { queryKey } = getBranchesInfiniteQueryOptions();
      queryClient.setQueryData(queryKey, (oldData) => {
        if (!oldData) return oldData;

        return {
          ...oldData,
          pages: oldData.pages.map((page) =>
            page.filter((branch) => branch.name !== branchDeleted)
          ),
        };
      });
      queryClient.invalidateQueries({ queryKey });
    },
  });
}
