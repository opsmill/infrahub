import { useMutation, useQueryClient } from "@tanstack/react-query";

import { rebaseBranch } from "@/entities/branches/domain/rebase-branch";
import { branchesQueryKeys } from "@/entities/branches/ui/queries/branch.query-keys";
import { tasksQueryKeys } from "@/entities/tasks/ui/queries/tasks.query-keys";

export const useRebaseBranch = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: rebaseBranch,
    onSuccess: () => {
      // A rebase rewrites branch history and enqueues a background task.
      queryClient.invalidateQueries({ queryKey: branchesQueryKeys.all });
      queryClient.invalidateQueries({ queryKey: tasksQueryKeys.all });
    },
  });
};
