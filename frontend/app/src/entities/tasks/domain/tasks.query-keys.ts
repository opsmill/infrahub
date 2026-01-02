import type { GetTasksHomepageParams } from "@/entities/tasks/domain/get-tasks/get-tasks-homepage.query";

export const tasksQueryKeys = {
  all: ["tasks"] as const,
  filters: (filters: GetTasksHomepageParams) => [
    ...tasksQueryKeys.all,
    filters?.branchName,
    filters?.states,
    filters?.search,
    filters?.relatedNodes,
    filters?.offset,
    filters?.limit,
  ],
};
