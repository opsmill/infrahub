import { useMutation, useQueryClient } from "@tanstack/react-query";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { type RunGeneratorParams, runGenerator } from "@/entities/generators/domain/run-generator";
import { tasksQueryKeys } from "@/entities/tasks/ui/queries/tasks.query-keys";

export const useRunGeneratorMutation = () => {
  const queryClient = useQueryClient();
  const { currentBranch } = useCurrentBranch();

  return useMutation({
    mutationFn: (params: Omit<RunGeneratorParams, "branchName">) => {
      return runGenerator({
        branchName: currentBranch.name,
        ...params,
      });
    },
    onSuccess: () => {
      // Generator runs enqueue a background task whose status is consumed
      // through `tasksQueryKeys` queries (the task list / details).
      queryClient.invalidateQueries({ queryKey: tasksQueryKeys.all });
    },
  });
};
