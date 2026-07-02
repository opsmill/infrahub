import { queryOptions } from "@tanstack/react-query";

import { isTaskRunningOnBranch } from "@/entities/tasks/domain/is-task-running-on-branch/is-task-running-on-branch";
import { tasksQueryKeys } from "@/entities/tasks/ui/queries/tasks.query-keys";

export const isTaskRunningOnBranchQueryOptions = (branch: string) => {
  return queryOptions({
    queryKey: tasksQueryKeys.isRunning(branch),
    queryFn: () => isTaskRunningOnBranch(branch),
  });
};
