import { useMutation } from "@tanstack/react-query";

import { queryClient } from "@/shared/api/rest/client";
import { store } from "@/shared/stores";

import { deleteBranch } from "@/entities/branches/domain/delete-branch";
import { branchesState } from "@/entities/branches/stores";
import { branchesQueryKeys } from "@/entities/branches/ui/queries/branch.query-keys";
import { getBranchesInfiniteQueryOptions } from "@/entities/branches/ui/queries/get-branches.query";

export function useDeleteBranchMutation() {
  return useMutation({
    mutationFn: deleteBranch,
    onSuccess: async (branchDeleted) => {
      if (!branchDeleted) return;

      store.set(branchesState, (prev) => prev.filter((b) => b.name !== branchDeleted));

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
      await queryClient.invalidateQueries({ queryKey: branchesQueryKeys.all });
    },
  });
}
