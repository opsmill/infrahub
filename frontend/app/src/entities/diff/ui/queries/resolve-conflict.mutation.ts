import { useMutation } from "@tanstack/react-query";

import type { ResolveConflictFromApiParams } from "@/entities/diff/api/resolve-conflict-from-api";
import { resolveConflict } from "@/entities/diff/domain/resolve-conflict";

export function useResolveConflictMutation() {
  return useMutation({
    mutationFn: (params: ResolveConflictFromApiParams) => resolveConflict(params),
  });
}
