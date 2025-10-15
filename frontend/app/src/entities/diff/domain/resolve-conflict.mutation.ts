import { useMutation } from "@tanstack/react-query";

import {
  type ResolveConflictParams,
  resolveConflict,
} from "@/entities/diff/domain/resolve-conflict";

export function useResolveConflictMutation() {
  return useMutation({
    mutationFn: (params: ResolveConflictParams) => resolveConflict(params),
  });
}
