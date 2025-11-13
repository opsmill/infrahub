import type { TaskNode, TaskNodes } from "@/shared/api/graphql/generated/graphql";

import {
  type GetTasksHomepageFromApiParams,
  getTasksHomepageFromApi,
} from "@/entities/tasks/api/get-tasks-homepage-from-api";

export type GetTasks = (params: GetTasksHomepageFromApiParams) => Promise<TaskNode[]>;

export const getTasks: GetTasks = async (params) => {
  const { data } = await getTasksHomepageFromApi(params);

  return data.InfrahubTask.edges.map((edge: TaskNodes) => edge.node);
};
