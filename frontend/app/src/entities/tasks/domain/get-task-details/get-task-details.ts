import {
  type GetTaskDetailsFromApiParams,
  getTaskDetailsFromApi,
} from "@/entities/tasks/api/get-task-details-from-api";

export type GetTaskDetailsParams = GetTaskDetailsFromApiParams;

export type TaskDetailsNode = Awaited<ReturnType<typeof getTaskDetails>>[0];

export async function getTaskDetails(params?: GetTaskDetailsParams) {
  const { data, errors } = await getTaskDetailsFromApi(params);

  if (errors) {
    throw new Error(errors.map((e) => e.message).join("; "));
  }

  return data.InfrahubTask.edges.map(({ node }) => node).filter((n) => !!n);
}
