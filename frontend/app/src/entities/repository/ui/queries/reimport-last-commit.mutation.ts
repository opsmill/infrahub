import { useMutation, useQueryClient } from "@tanstack/react-query";

import type { BranchContextParams, MutationConfig } from "@/shared/api/types";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import {
  type ReimportLastCommitParams,
  reimportLastCommit,
} from "@/entities/repository/domain/use-cases/reimport-last-commit";
import { repositoriesQueryKeys } from "@/entities/repository/ui/queries/repository.query-keys";

interface ReimportLastCommitProps extends MutationConfig<typeof reimportLastCommit> {}

export const REIMPORT_LAST_COMMIT_MUTATION_KEY = ["repository", "reimport-last-commit"] as const;

// invalidation-at-callsite: this hook intentionally accepts a `config` argument
// so each caller chooses which queries to invalidate (e.g.
// repository-menu-section.tsx invalidates `objectQueryKeys.all` on success).
export function useReimportLastCommitMutation(
  config?: Omit<ReimportLastCommitProps, "mutationFn">
) {
  const { currentBranch } = useCurrentBranch();
  const queryClient = useQueryClient();

  return useMutation({
    mutationKey: REIMPORT_LAST_COMMIT_MUTATION_KEY,
    mutationFn: (params: Omit<ReimportLastCommitParams, keyof BranchContextParams>) => {
      return reimportLastCommit({ branchName: currentBranch.name, ...params });
    },
    ...config,
    // The card shows the started run at once instead of at its next idle check.
    onSuccess: (...args) => {
      queryClient.invalidateQueries({
        queryKey: repositoriesQueryKeys.activity({ repositoryId: args[1].repositoryId }),
      });
      return config?.onSuccess?.(...args);
    },
  });
}
