import { type InfiniteData, useMutation } from "@tanstack/react-query";

import { queryClient } from "@/shared/api/rest/client";
import { store } from "@/shared/stores";

import type { BranchDetail, BranchListItem } from "@/entities/branches/domain/branch.mappers";
import { updateBranch } from "@/entities/branches/domain/update-branch";
import { branchesState } from "@/entities/branches/stores";
import { branchesQueryKeys } from "@/entities/branches/ui/queries/branch.query-keys";

export function useUpdateBranchMutation() {
  return useMutation({
    mutationFn: updateBranch,
    onSuccess: async (ok, { name, description }) => {
      if (!ok) return;

      store.set(branchesState, (prev) =>
        prev.map((b) => (b.name === name ? { ...b, description } : b))
      );

      queryClient.setQueryData<BranchDetail>(
        branchesQueryKeys.details({ branchName: name }),
        (old) => (old ? { ...old, description } : old)
      );

      queryClient.setQueriesData<InfiniteData<BranchListItem[]>>(
        { queryKey: [...branchesQueryKeys.all, "list"] },
        (oldData) => {
          if (!oldData) return oldData;
          return {
            ...oldData,
            pages: oldData.pages.map((page) =>
              page.map((b) => (b.name === name ? { ...b, description } : b))
            ),
          };
        }
      );

      await queryClient.invalidateQueries({ queryKey: branchesQueryKeys.all });
    },
  });
}
