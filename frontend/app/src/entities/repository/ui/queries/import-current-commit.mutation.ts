import { useMutation, useQueryClient } from "@tanstack/react-query";

import type { BranchContextParams, MutationConfig } from "@/shared/api/types";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import {
  type ImportCurrentCommitParams,
  importCurrentCommit,
} from "@/entities/repository/domain/use-cases/import-current-commit";
import { repositoriesQueryKeys } from "@/entities/repository/ui/queries/repository.query-keys";

interface ImportCurrentCommitProps extends MutationConfig<typeof importCurrentCommit> {}

export const IMPORT_CURRENT_COMMIT_MUTATION_KEY = ["repository", "import-current-commit"] as const;

// invalidation-at-callsite: this hook intentionally accepts a `config` argument
// so each caller chooses which queries to invalidate (e.g.
// repository-menu-section.tsx invalidates `objectQueryKeys.all` on success).
export function useImportCurrentCommitMutation(
  config?: Omit<ImportCurrentCommitProps, "mutationFn">
) {
  const { currentBranch } = useCurrentBranch();
  const queryClient = useQueryClient();

  return useMutation({
    mutationKey: IMPORT_CURRENT_COMMIT_MUTATION_KEY,
    mutationFn: (
      params: Omit<ImportCurrentCommitParams, keyof BranchContextParams> &
        Partial<BranchContextParams>
    ) => {
      return importCurrentCommit({
        ...params,
        branchName: params.branchName ?? currentBranch.name,
      });
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
