import type { GetTasksParams } from "./get-tasks/get-tasks.query";

export const tasksQueryKeys = {
  all: ["tasks"] as const,
  filters: (filters: GetTasksParams) => [
    filters?.branchName,
    filters?.states,
    filters?.search,
    filters?.relatedNodes,
    filters?.offset,
    filters?.limit,
  ],
};
