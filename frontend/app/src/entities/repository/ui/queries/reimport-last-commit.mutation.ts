import { useMutation } from "@tanstack/react-query";

import type { BranchContextParams, MutationConfig } from "@/shared/api/types";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import {
  type ReimportLastCommitParams,
  reimportLastCommit,
} from "@/entities/repository/domain/reimport-last-commit";

interface ReimportLastCommitProps extends MutationConfig<typeof reimportLastCommit> {}

export const REIMPORT_LAST_COMMIT_MUTATION_KEY = ["repository", "reimport-last-commit"] as const;

export function useReimportLastCommitMutation(
  config?: Omit<ReimportLastCommitProps, "mutationFn">
) {
  const { currentBranch } = useCurrentBranch();

  return useMutation({
    mutationKey: REIMPORT_LAST_COMMIT_MUTATION_KEY,
    mutationFn: (params: Omit<ReimportLastCommitParams, keyof BranchContextParams>) => {
      return reimportLastCommit({ branchName: currentBranch.name, ...params });
    },
    ...config,
  });
}
