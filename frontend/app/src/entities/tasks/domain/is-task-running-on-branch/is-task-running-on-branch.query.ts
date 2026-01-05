import { queryOptions } from "@tanstack/react-query";

import { isTaskRunningOnBranch } from "@/entities/tasks/domain/is-task-running-on-branch/is-task-running-on-branch";

export const isTaskRunningOnBranchQueryOptions = (branch: string) => {
  return queryOptions({
    queryKey: [branch, "is-task-running"],
    queryFn: () => isTaskRunningOnBranch(branch),
  });
};
