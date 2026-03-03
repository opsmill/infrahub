import { useMutation } from "@tanstack/react-query";

import { updateDiff } from "@/entities/diff/domain/update-diff";
import { updateDiffMutationKeys } from "@/entities/diff/ui/queries/diff.query-keys";

export function useUpdateDiffMutation() {
  return useMutation({
    mutationKey: updateDiffMutationKeys.all,
    mutationFn: (branchName: string) => updateDiff(branchName),
  });
}
