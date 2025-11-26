import type { TaskNode, TaskNodes } from "@/shared/api/graphql/generated/graphql";

import {
  type GetTasksFromApiParams,
  getTasksFromApi,
} from "@/entities/tasks/api/get-tasks-from-api";

export type GetTasks = (params: GetTasksFromApiParams) => Promise<TaskNode[]>;

export const getTasks: GetTasks = async (params) => {
  const { data } = await getTasksFromApi(params);

  return data.InfrahubTask.edges.map((edge: TaskNodes) => edge.node);
};
