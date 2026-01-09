import { useMutation } from "@tanstack/react-query";

import { queryClient } from "@/shared/api/rest/client";

import { branchesQueryKeys } from "@/entities/branches/domain/branch.query-keys";
import { deleteBranches } from "@/entities/branches/domain/delete-branches";
import { getBranchesInfiniteQueryOptions } from "@/entities/branches/domain/get-branches.query";

export function useDeleteBranchesMutation() {
  return useMutation({
    mutationFn: deleteBranches,
    onSuccess: async (result) => {
      if (result.deleted.length === 0) return;

      const { queryKey } = getBranchesInfiniteQueryOptions();
      queryClient.setQueryData(queryKey, (oldData) => {
        if (!oldData) return oldData;

        return {
          ...oldData,
          pages: oldData.pages.map((page) =>
            page.filter((branch) => !result.deleted.includes(branch.name))
          ),
        };
      });

      await queryClient.invalidateQueries({ queryKey: branchesQueryKeys.all });
    },
  });
}
