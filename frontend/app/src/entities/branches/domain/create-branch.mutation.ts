import { useMutation } from "@tanstack/react-query";

import type { Branch } from "@/shared/api/graphql/generated/graphql";
import { queryClient } from "@/shared/api/rest/client";

import { branchesQueryKeys } from "@/entities/branches/domain/branch.query-keys";
import { type CreateBranchParams, createBranch } from "@/entities/branches/domain/create-branch";

export function useCreateBranchMutation() {
  return useMutation({
    mutationFn: createBranch,
    onMutate: async (params: CreateBranchParams) => {
      await queryClient.cancelQueries({ queryKey: branchesQueryKeys.all });

      const previousBranches = queryClient.getQueryData<Branch[]>(branchesQueryKeys.all);

      queryClient.setQueryData<Branch[]>(branchesQueryKeys.all, (old) => [
        ...(old ?? []),
        {
          id: params.name,
          name: params.name,
          description: params.description ?? "",
          is_default: false,
          sync_with_git: params.sync_with_git ?? false,
          branched_from: "",
          created_at: new Date().toISOString(),
        } as Branch,
      ]);

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
