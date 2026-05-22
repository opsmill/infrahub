import { objectQueryKeys } from "@/entities/nodes/object/ui/queries/object.query-keys";
import type { CheckTaskDetailsParams } from "@/entities/tasks/domain/check-task-details/check-task-details";
import type { GetTaskDetailsParams } from "@/entities/tasks/domain/get-task-details/get-task-details";
import type { GetTaskDetailsTitleParams } from "@/entities/tasks/domain/get-task-details-title/get-task-details-title";
import type { GetTaskListParams } from "@/entities/tasks/domain/get-task-list/get-task-list";

export const tasksQueryKeys = {
  all: [...objectQueryKeys.all, "tasks"] as const,
  list: (filters?: GetTaskListParams) => [...tasksQueryKeys.all, filters],
  count: (filters?: GetTaskListParams) => [...tasksQueryKeys.list(filters), "count"],
  homepage: (filters?: GetTaskListParams) => [...tasksQueryKeys.list(filters), "homepage"],
  details: (params?: GetTaskDetailsParams) => [...tasksQueryKeys.all, "details", params] as const,
  detailsTitle: (params: GetTaskDetailsTitleParams) =>
    [...tasksQueryKeys.all, "details-title", params] as const,
  check: (params?: CheckTaskDetailsParams) => [...tasksQueryKeys.all, "check", params] as const,
};
