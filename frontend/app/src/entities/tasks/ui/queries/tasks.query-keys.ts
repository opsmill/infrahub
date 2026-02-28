import { objectQueryKeys } from "@/entities/nodes/object/ui/queries/object.query-keys";
import type { GetTaskListParams } from "@/entities/tasks/domain/get-task-list/get-task-list";

export const tasksQueryKeys = {
  all: [...objectQueryKeys.all, "tasks"] as const,
  list: (filters?: GetTaskListParams) => [...tasksQueryKeys.all, filters],
  count: (filters?: GetTaskListParams) => [...tasksQueryKeys.list(filters), "count"],
  homepage: (filters?: GetTaskListParams) => [...tasksQueryKeys.list(filters), "homepage"],
};
