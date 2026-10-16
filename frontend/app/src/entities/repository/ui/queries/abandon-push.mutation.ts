import { useMutation, useQueryClient } from "@tanstack/react-query";

import type { BranchContextParams, MutationConfig } from "@/shared/api/types";

import { useDefaultBranch } from "@/entities/branches/ui/hooks/use-default-branch";
import {
  type AbandonPushParams,
  abandonPush,
} from "@/entities/repository/domain/use-cases/abandon-push";
import { repositoriesQueryKeys } from "@/entities/repository/ui/queries/repository.query-keys";

interface AbandonPushProps extends MutationConfig<typeof abandonPush> {}

export const ABANDON_PUSH_MUTATION_KEY = ["repository", "abandon-push"] as const;

// The pending pushes live on the default branch, and the backend refuses to abandon from any other.
export function useAbandonPushMutation(config?: Omit<AbandonPushProps, "mutationFn">) {
  const defaultBranch = useDefaultBranch();
  const queryClient = useQueryClient();

  return useMutation({
    mutationKey: ABANDON_PUSH_MUTATION_KEY,
    mutationFn: (params: Omit<AbandonPushParams, keyof BranchContextParams>) => {
      if (!defaultBranch) {
        throw new Error("The default branch is not loaded.");
      }
      return abandonPush({ branchName: defaultBranch.name, ...params });
    },
    ...config,
    // A refused request means the state shown is out of date, so it reloads either way.
    onSettled: (...args) => {
      const { repositoryId } = args[2];
      queryClient.invalidateQueries({
        queryKey: repositoriesQueryKeys.pushState({ repositoryId }),
      });
      queryClient.invalidateQueries({ queryKey: repositoriesQueryKeys.activity({ repositoryId }) });
      return config?.onSettled?.(...args);
    },
  });
}
