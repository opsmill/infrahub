import { useMutation, useQueryClient } from "@tanstack/react-query";

import { updateDiff } from "@/entities/diff/domain/update-diff";
import {
  diffSummaryKeys,
  treeQueryKeys,
  updateDiffMutationKeys,
} from "@/entities/diff/ui/queries/diff.query-keys";

export function useUpdateDiffMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationKey: updateDiffMutationKeys.all,
    mutationFn: (branchName: string) => updateDiff(branchName),
    onSuccess: () => {
      // A diff refresh changes both the tree view and the summary; every
      // caller needs both invalidated (diff-rebase-button.tsx used to forget
      // this — Option 1 ensures the rebase flow gets it for free).
      queryClient.invalidateQueries({ queryKey: treeQueryKeys.all });
      queryClient.invalidateQueries({ queryKey: diffSummaryKeys.all });
    },
  });
}
