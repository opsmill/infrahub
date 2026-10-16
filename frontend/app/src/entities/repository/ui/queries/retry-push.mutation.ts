import { useMutation } from "@tanstack/react-query";

import type { BranchContextParams, MutationConfig } from "@/shared/api/types";

import { useDefaultBranch } from "@/entities/branches/ui/hooks/use-default-branch";
import { type RetryPushParams, retryPush } from "@/entities/repository/domain/use-cases/retry-push";

interface RetryPushProps extends MutationConfig<typeof retryPush> {}

export const RETRY_PUSH_MUTATION_KEY = ["repository", "retry-push"] as const;

// The pending pushes live on the default branch, and the backend refuses a retry sent on any other.
// invalidation-at-callsite: the caller invalidates `objectQueryKeys.all` with its own toast.
export function useRetryPushMutation(config?: Omit<RetryPushProps, "mutationFn">) {
  const defaultBranch = useDefaultBranch();

  return useMutation({
    mutationKey: RETRY_PUSH_MUTATION_KEY,
    mutationFn: (params: Omit<RetryPushParams, keyof BranchContextParams>) => {
      if (!defaultBranch) {
        throw new Error("The default branch is not loaded.");
      }
      return retryPush({ branchName: defaultBranch.name, ...params });
    },
    ...config,
  });
}
