import { useMutation } from "@tanstack/react-query";

import type { BranchContextParams, MutationConfig } from "@/shared/api/types";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import {
  type CheckRemoteRefsParams,
  checkRemoteRefs,
} from "@/entities/repository/domain/use-cases/check-remote-refs";

interface CheckRemoteRefsProps extends MutationConfig<typeof checkRemoteRefs> {}

export const CHECK_REMOTE_REFS_MUTATION_KEY = ["repository", "check-remote-refs"] as const;

// invalidation-at-callsite: the check runs as a task after this mutation returns, so the commit
// log only changes once that task ends; the callsite refetches it then.
export function useCheckRemoteRefsMutation(config?: Omit<CheckRemoteRefsProps, "mutationFn">) {
  const { currentBranch } = useCurrentBranch();

  return useMutation({
    mutationKey: CHECK_REMOTE_REFS_MUTATION_KEY,
    mutationFn: (params: Omit<CheckRemoteRefsParams, keyof BranchContextParams>) => {
      return checkRemoteRefs({ branchName: currentBranch.name, ...params });
    },
    ...config,
  });
}
