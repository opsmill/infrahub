import type { GetTasksFromApiParams } from "@/entities/tasks/api/get-tasks-from-api";

export const tasksQueryKeys = {
  all: ["tasks"] as const,
  filters: (filters: GetTasksFromApiParams) => [
    filters?.branchName,
    filters?.states,
    filters?.search,
    filters?.relatedNodes,
    filters?.offset,
    filters?.limit,
  ],
};
