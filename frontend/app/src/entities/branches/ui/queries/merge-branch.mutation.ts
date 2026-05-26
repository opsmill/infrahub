import { useMutation, useQueryClient } from "@tanstack/react-query";

import { mergeBranch } from "@/entities/branches/domain/merge-branch";
import { branchesQueryKeys } from "@/entities/branches/ui/queries/branch.query-keys";
import { tasksQueryKeys } from "@/entities/tasks/ui/queries/tasks.query-keys";

export function useMergeBranch() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: mergeBranch,
    onSuccess: () => {
      // A merge changes branch status and enqueues a background task.
      queryClient.invalidateQueries({ queryKey: branchesQueryKeys.all });
      queryClient.invalidateQueries({ queryKey: tasksQueryKeys.all });
    },
  });
}
