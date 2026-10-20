import { useMutation, useQueryClient } from "@tanstack/react-query";

import { branchGitStatusQueryKeys } from "@/entities/branch-git-status/ui/queries/branch-git-status.query-keys";
import { mergeBranch } from "@/entities/branches/domain/use-cases/merge-branch";
import { branchesQueryKeys } from "@/entities/branches/ui/queries/branch.query-keys";
import { tasksQueryKeys } from "@/entities/tasks/ui/queries/tasks.query-keys";

export function useMergeBranch() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: mergeBranch,
    onSuccess: () => {
      // The merge runs as a background task, so this refresh shows only its start.
      queryClient.invalidateQueries({ queryKey: branchesQueryKeys.all });
      queryClient.invalidateQueries({ queryKey: tasksQueryKeys.all });
      queryClient.invalidateQueries({ queryKey: branchGitStatusQueryKeys.all });
    },
  });
}
