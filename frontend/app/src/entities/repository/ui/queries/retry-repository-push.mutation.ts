import { useMutation, useQueryClient } from "@tanstack/react-query";

import type { BranchContextParams, MutationConfig } from "@/shared/api/types";

import { useDefaultBranch } from "@/entities/branches/ui/hooks/use-default-branch";
import {
  type RetryRepositoryPushParams,
  retryRepositoryPush,
} from "@/entities/repository/domain/use-cases/retry-repository-push";
import { repositoriesQueryKeys } from "@/entities/repository/ui/queries/repository.query-keys";

interface RetryRepositoryPushProps extends MutationConfig<typeof retryRepositoryPush> {}

export const RETRY_REPOSITORY_PUSH_MUTATION_KEY = ["repository", "retry-repository-push"] as const;

// The pending pushes live on the default branch, and the backend refuses a retry sent on any other.
export function useRetryRepositoryPushMutation(
  config?: Omit<RetryRepositoryPushProps, "mutationFn">
) {
  const defaultBranch = useDefaultBranch();
  const queryClient = useQueryClient();

  return useMutation({
    mutationKey: RETRY_REPOSITORY_PUSH_MUTATION_KEY,
    mutationFn: (params: Omit<RetryRepositoryPushParams, keyof BranchContextParams>) => {
      if (!defaultBranch) {
        throw new Error("The default branch is not loaded.");
      }
      return retryRepositoryPush({ branchName: defaultBranch.name, ...params });
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
