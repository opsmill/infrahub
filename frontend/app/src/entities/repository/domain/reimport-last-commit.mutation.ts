import { useMutation } from "@tanstack/react-query";

import type { MutationConfig } from "@/shared/api/types";

import {
  type ReimportLastCommitParams,
  reimportLastCommit,
} from "@/entities/repository/domain/reimport-last-commit";

interface ReimportLastCommitProps extends MutationConfig<typeof reimportLastCommit> {}

export const REIMPORT_LAST_COMMIT_MUTATION_KEY = ["repository", "reimport-last-commit"] as const;

export function useReimportLastCommitMutation(
  config?: Omit<ReimportLastCommitProps, "mutationFn">
) {
  return useMutation({
    mutationKey: REIMPORT_LAST_COMMIT_MUTATION_KEY,
    mutationFn: (params: ReimportLastCommitParams) => {
      return reimportLastCommit(params);
    },
    ...config,
  });
}
