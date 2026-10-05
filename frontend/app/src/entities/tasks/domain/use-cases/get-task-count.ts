import {
  type GetTaskCountFromApiParams,
  getTaskCountFromApi,
} from "@/entities/tasks/api/get-task-count-from-api";
import type { TaskQueryOptions } from "@/entities/tasks/api/get-task-list-from-api";

export interface GetTaskCountParams extends GetTaskCountFromApiParams {}

export type GetTaskCount = (
  params?: GetTaskCountParams,
  options?: TaskQueryOptions
) => Promise<number>;

export const getTaskCount: GetTaskCount = async (params, options) => {
  const { data, errors } = await getTaskCountFromApi(params, options);

  if (errors) {
    throw new Error(errors.map((e) => e.message).join("; "));
  }

  return data.InfrahubTask.count;
};
