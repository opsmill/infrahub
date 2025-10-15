import { useMutation } from "@tanstack/react-query";

import { resolveConflict } from "@/entities/diff/domain/resolve-conflict";

import type { ResolveConflictFromApiParams } from "../api/resolve-conflict-from-api";

export function useResolveConflictMutation() {
  return useMutation({
    mutationFn: (params: ResolveConflictFromApiParams) => resolveConflict(params),
  });
}
