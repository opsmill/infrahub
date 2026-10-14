import { useMutation } from "@tanstack/react-query";

import {
  type CheckRemoteRefsParams,
  checkRemoteRefs,
} from "@/entities/repository/domain/use-cases/check-remote-refs";

export const CHECK_REMOTE_REFS_MUTATION_KEY = ["repository", "check-remote-refs"] as const;

// invalidation-at-callsite: the mutation only starts a task, so nothing changes when it returns; the
// poll of that task refetches the commit log once the task ends.
export function useCheckRemoteRefsMutation() {
  return useMutation({
    mutationKey: CHECK_REMOTE_REFS_MUTATION_KEY,
    mutationFn: (params: CheckRemoteRefsParams) => checkRemoteRefs(params),
  });
}
