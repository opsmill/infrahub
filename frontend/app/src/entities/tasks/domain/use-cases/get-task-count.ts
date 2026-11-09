import {
  type GetTaskCountFromApiParams,
  getTaskCountFromApi,
} from "@/entities/tasks/api/get-task-count-from-api";

export interface GetTaskCountParams extends GetTaskCountFromApiParams {}

export type GetTaskCount = (params?: GetTaskCountParams) => Promise<number>;

export const getTaskCount: GetTaskCount = async (params) => {
  const { data, errors } = await getTaskCountFromApi(params);

  if (errors) {
    throw new Error(errors.map((e) => e.message).join("; "));
  }

  return data.InfrahubTask.count;
};
