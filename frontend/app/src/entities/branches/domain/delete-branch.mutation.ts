import { useMutation } from "@tanstack/react-query";

import type { Branch } from "@/shared/api/graphql/generated/graphql";
import { queryClient } from "@/shared/api/rest/client";

import { branchesQueryKeys } from "@/entities/branches/domain/branch.query-keys";
import { type DeleteBranchParams, deleteBranch } from "@/entities/branches/domain/delete-branch";

export function useDeleteBranchMutation() {
  return useMutation({
    mutationFn: deleteBranch,
    onMutate: async ({ name }: DeleteBranchParams) => {
      await queryClient.cancelQueries({ queryKey: branchesQueryKeys.all });

      const previousBranches = queryClient.getQueryData<Branch[]>(branchesQueryKeys.all);

      queryClient.setQueryData<Branch[]>(branchesQueryKeys.all, (old) =>
        old?.filter((branch) => branch.name !== name)
      );

      return { previousBranches };
    },
    onError: (_err, _variables, context) => {
      if (context?.previousBranches) {
        queryClient.setQueryData(branchesQueryKeys.all, context.previousBranches);
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: branchesQueryKeys.all });
    },
  });
}
