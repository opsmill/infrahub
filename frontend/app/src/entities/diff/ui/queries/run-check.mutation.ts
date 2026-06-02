import { useMutation } from "@tanstack/react-query";

import { runCheck } from "@/entities/diff/domain/run-check";

// invalidation-at-callsite: callers pass an explicit `onSuccess` (see
// checks-summary.tsx) that invalidates `proposedChangeValidatorsKeys` for the
// proposed change being viewed. The query key needs runtime context that this
// hook does not have.
export function useRunCheckMutation() {
  return useMutation({
    mutationFn: runCheck,
  });
}
