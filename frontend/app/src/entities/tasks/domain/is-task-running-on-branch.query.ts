import { isTaskRunningOnBranch } from "@/entities/tasks/domain/is-task-running-on-branch";
import { queryOptions } from "@tanstack/react-query";

export const isTaskRunningOnBranchQueryOptions = (branch: string) => {
  return queryOptions({
    queryKey: ["is-task-running", branch],
    queryFn: () => isTaskRunningOnBranch(branch),
  });
};
