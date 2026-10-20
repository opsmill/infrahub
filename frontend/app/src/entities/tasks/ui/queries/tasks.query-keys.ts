import type { CheckTaskDetailsParams } from "@/entities/tasks/domain/use-cases/check-task-details";
import type { GetBranchTasksParams } from "@/entities/tasks/domain/use-cases/get-branch-tasks";
import type { GetTaskDetailsParams } from "@/entities/tasks/domain/use-cases/get-task-details";
import type { GetTaskDetailsTitleParams } from "@/entities/tasks/domain/use-cases/get-task-details-title";
import type { GetTaskListParams } from "@/entities/tasks/domain/use-cases/get-task-list";
import type { IsTaskFinishedParams } from "@/entities/tasks/domain/use-cases/is-task-finished";

export const tasksQueryKeys = {
  all: ["tasks"] as const,
  isRunning: (branch: string) => [...tasksQueryKeys.all, "is-task-running", branch] as const,
  list: (filters?: GetTaskListParams) => [...tasksQueryKeys.all, filters] as const,
  count: (filters?: GetTaskListParams) => [...tasksQueryKeys.list(filters), "count"] as const,
  branchListOnBranch: (params: Pick<GetBranchTasksParams, "branchName">) =>
    [...tasksQueryKeys.all, "branch-list", params] as const,
  branchList: (params: GetBranchTasksParams) =>
    [...tasksQueryKeys.all, "branch-list", params] as const,
  homepage: (filters?: GetTaskListParams) => [...tasksQueryKeys.list(filters), "homepage"] as const,
  details: (params?: GetTaskDetailsParams) => [...tasksQueryKeys.all, "details", params] as const,
  detailsTitle: (params: GetTaskDetailsTitleParams) =>
    [...tasksQueryKeys.all, "details-title", params] as const,
  check: (params?: CheckTaskDetailsParams) => [...tasksQueryKeys.all, "check", params] as const,
  finished: (params: IsTaskFinishedParams) => [...tasksQueryKeys.all, "finished", params] as const,
};
