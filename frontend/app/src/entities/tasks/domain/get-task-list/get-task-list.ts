import {
  type GetTaskListFromApiParams,
  getTaskListFromApi,
} from "@/entities/tasks/api/get-task-list-from-api";

export type GetTaskListParams = GetTaskListFromApiParams;

export const getTaskList = async (params?: GetTaskListParams) => {
  const { data, errors } = await getTaskListFromApi(params);

  if (errors) {
    throw new Error(errors.map((e) => e.message).join("; "));
  }

  return data.InfrahubTask.edges.map(({ node }) => node).filter((n) => !!n);
};
