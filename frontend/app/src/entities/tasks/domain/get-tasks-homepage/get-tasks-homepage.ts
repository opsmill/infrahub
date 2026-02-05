import {
  type GetTasksHomepageFromApiParams,
  getTasksHomepageFromApi,
} from "@/entities/tasks/api/get-tasks-homepage-from-api";

export type GetTasksHomepageParams = GetTasksHomepageFromApiParams;
export type TaskHomepageNode = Awaited<ReturnType<typeof getTasksHomepage>>[0];

export const getTasksHomepage = async (params: GetTasksHomepageParams) => {
  const { data } = await getTasksHomepageFromApi(params);

  return data.InfrahubTask.edges.map((edge) => edge.node).filter((n) => !!n);
};
