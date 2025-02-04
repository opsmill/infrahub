import { updateDiff } from "@/entities/diff/domain/update-diff";
import { useMutation } from "@tanstack/react-query";

export function useUpdateDiffMutation() {
  return useMutation({
    mutationFn: (branchName: string) => updateDiff(branchName),
  });
}
