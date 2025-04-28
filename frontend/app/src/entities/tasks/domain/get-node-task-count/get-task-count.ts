import { getTaskCountFromApi } from "@/entities/tasks/api/get-task-count-from-api";

export type GetTaskCountParams = {
  nodeId: string;
};

export type GetTaskCount = (params: GetTaskCountParams) => Promise<number>;

export const getTaskCount: GetTaskCount = async ({ nodeId }) => {
  const { data } = await getTaskCountFromApi([nodeId]);

  return data.InfrahubTask.count;
};
