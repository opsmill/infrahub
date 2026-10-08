import { useMutation } from "@tanstack/react-query";

import type { MutationConfig } from "@/shared/api/types";

import {
  type CheckRemoteRefsParams,
  checkRemoteRefs,
} from "@/entities/repository/domain/use-cases/check-remote-refs";

interface CheckRemoteRefsProps extends MutationConfig<typeof checkRemoteRefs> {}

export const CHECK_REMOTE_REFS_MUTATION_KEY = ["repository", "check-remote-refs"] as const;

// The started task is read back from this mutation, so it must outlive the default five minutes
// once its button unmounts, or a long check is forgotten when the tab comes back.
const CHECK_REMOTE_REFS_GC_TIME_MS = 30 * 60 * 1000;

// invalidation-at-callsite: the mutation only starts a task, so there is nothing to invalidate
// when it returns; the poll of that task refetches the commit log once the task ends.
export function useCheckRemoteRefsMutation(config?: Omit<CheckRemoteRefsProps, "mutationFn">) {
  return useMutation({
    mutationKey: CHECK_REMOTE_REFS_MUTATION_KEY,
    mutationFn: (params: CheckRemoteRefsParams) => checkRemoteRefs(params),
    gcTime: CHECK_REMOTE_REFS_GC_TIME_MS,
    ...config,
  });
}
