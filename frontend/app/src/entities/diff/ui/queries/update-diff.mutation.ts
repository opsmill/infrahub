import { useMutation } from "@tanstack/react-query";

import { updateDiffMutationKeys } from "@/entities/diff/ui/queries/diff.query-keys";
import { updateDiff } from "@/entities/diff/domain/update-diff";

export function useUpdateDiffMutation() {
  return useMutation({
    mutationKey: updateDiffMutationKeys.all,
    mutationFn: (branchName: string) => updateDiff(branchName),
  });
}
