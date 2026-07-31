import { useMutation, useQueryClient } from "@tanstack/react-query";

import { validateBranch } from "@/entities/branches/domain/validate-branch";
import { branchesQueryKeys } from "@/entities/branches/ui/queries/branch.query-keys";
import { tasksQueryKeys } from "@/entities/tasks/ui/queries/tasks.query-keys";

export function useValidateBranch() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: validateBranch,
    onSuccess: () => {
      // Validation refreshes branch action-state and runs a background task.
      queryClient.invalidateQueries({ queryKey: branchesQueryKeys.all });
      queryClient.invalidateQueries({ queryKey: tasksQueryKeys.all });
    },
  });
}
