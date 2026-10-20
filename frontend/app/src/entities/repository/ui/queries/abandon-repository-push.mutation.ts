import { useMutation, useQueryClient } from "@tanstack/react-query";

import type { BranchContextParams, MutationConfig } from "@/shared/api/types";

import { useDefaultBranch } from "@/entities/branches/ui/hooks/use-default-branch";
import {
  type AbandonRepositoryPushParams,
  abandonRepositoryPush,
} from "@/entities/repository/domain/use-cases/abandon-repository-push";
import { repositoriesQueryKeys } from "@/entities/repository/ui/queries/repository.query-keys";

interface AbandonRepositoryPushProps extends MutationConfig<typeof abandonRepositoryPush> {}

export const ABANDON_REPOSITORY_PUSH_MUTATION_KEY = [
  "repository",
  "abandon-repository-push",
] as const;

// The pending pushes live on the default branch, and the backend refuses to abandon from any other.
export function useAbandonRepositoryPushMutation(
  config?: Omit<AbandonRepositoryPushProps, "mutationFn">
) {
  const defaultBranch = useDefaultBranch();
  const queryClient = useQueryClient();

  return useMutation({
    mutationKey: ABANDON_REPOSITORY_PUSH_MUTATION_KEY,
    mutationFn: (params: Omit<AbandonRepositoryPushParams, keyof BranchContextParams>) => {
      if (!defaultBranch) {
        throw new Error("The default branch is not loaded.");
      }
      return abandonRepositoryPush({ branchName: defaultBranch.name, ...params });
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
