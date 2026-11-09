import {
  type GetTaskDetailsTitleFromApiParams,
  getTaskDetailsTitleFromApi,
} from "@/entities/tasks/api/get-task-details-title-from-api";

export type GetTaskDetailsTitleParams = GetTaskDetailsTitleFromApiParams;

export async function getTaskDetailsTitle(params: GetTaskDetailsTitleParams) {
  const { data, errors } = await getTaskDetailsTitleFromApi(params);

  if (errors) {
    throw new Error(errors.map((e) => e.message).join("; "));
  }

  return data.InfrahubTask.edges[0]?.node ?? null;
}
