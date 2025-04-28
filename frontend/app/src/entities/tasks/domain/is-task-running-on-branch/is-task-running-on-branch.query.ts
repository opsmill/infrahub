import { isTaskRunningOnBranch } from "@/entities/tasks/domain/is-task-running-on-branch/is-task-running-on-branch";
import { queryOptions } from "@tanstack/react-query";

export const isTaskRunningOnBranchQueryOptions = (branch: string) => {
  return queryOptions({
    queryKey: [branch, "is-task-running"],
    queryFn: () => isTaskRunningOnBranch(branch),
  });
};
