import { useMutation } from "@tanstack/react-query";

import { resolveConflict, type ResolveConflictParams } from "./resolve-conflict";

export const RESOLVE_CONFLICT_KEY = "update-diff";

export function useResolveConflictMutation() {
  return useMutation({
    mutationKey: [RESOLVE_CONFLICT_KEY],
    mutationFn: (params: ResolveConflictParams) => resolveConflict(params),
  });
}
