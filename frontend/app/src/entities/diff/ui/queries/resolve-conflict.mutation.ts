import { useMutation } from "@tanstack/react-query";

import type { ResolveConflictFromApiParams } from "@/entities/diff/api/resolve-conflict-from-api";
import { resolveConflict } from "@/entities/diff/domain/resolve-conflict";

// invalidation-at-callsite: callers pass an explicit `onSuccess` (see
// conflict.tsx) that invalidates `treeQueryKeys.all` + `tasksQueryKeys.all`.
// Conflict resolution is always invoked inside a diff view, so a single
// shared invalidation here would not have enough context.
export function useResolveConflictMutation() {
  return useMutation({
    mutationFn: (params: ResolveConflictFromApiParams) => resolveConflict(params),
  });
}
