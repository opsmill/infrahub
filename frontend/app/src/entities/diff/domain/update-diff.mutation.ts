import { useMutation } from "@tanstack/react-query";

import { updateDiff } from "@/entities/diff/domain/update-diff";

export const UPDATE_DIFF_KEY = "update-diff";

export function useUpdateDiffMutation() {
  return useMutation({
    mutationKey: [UPDATE_DIFF_KEY],
    mutationFn: (branchName: string) => updateDiff(branchName),
  });
}
