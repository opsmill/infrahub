import { useMutation } from "@tanstack/react-query";

import { queryClient } from "@/shared/api/rest/client";
import { store } from "@/shared/stores";

import { branchesQueryKeys } from "@/entities/branches/ui/queries/branch.query-keys";
import { deleteBranches } from "@/entities/branches/domain/delete-branches";
import { getBranchesInfiniteQueryOptions } from "@/entities/branches/ui/queries/get-branches.query";
import { branchesState } from "@/entities/branches/stores";

export function useDeleteBranchesMutation() {
  return useMutation({
    mutationFn: deleteBranches,
    onSuccess: async (result) => {
      if (result.deleted.length === 0) return;

      store.set(branchesState, (prev) => prev.filter((b) => !result.deleted.includes(b.name)));

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
