import { useMutation } from "@tanstack/react-query";

import type { BranchContextParams, MutationConfig } from "@/shared/api/types";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import {
  type ImportCurrentCommitParams,
  importCurrentCommit,
} from "@/entities/repository/domain/import-current-commit";

interface ImportCurrentCommitProps extends MutationConfig<typeof importCurrentCommit> {}

export const IMPORT_CURRENT_COMMIT_MUTATION_KEY = ["repository", "import-current-commit"] as const;

export function useImportCurrentCommitMutation(
  config?: Omit<ImportCurrentCommitProps, "mutationFn">
) {
  const { currentBranch } = useCurrentBranch();

  return useMutation({
    mutationKey: IMPORT_CURRENT_COMMIT_MUTATION_KEY,
    mutationFn: (params: Omit<ImportCurrentCommitParams, keyof BranchContextParams>) => {
      return importCurrentCommit({ branchName: currentBranch.name, ...params });
    },
    ...config,
  });
}
