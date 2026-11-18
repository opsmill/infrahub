import {
  getTaskListFromApi,
  type TaskRequestOptions,
} from "@/entities/tasks/api/get-task-list-from-api";
import { toTaskListPage } from "@/entities/tasks/api/task-list.mappers";
import type { TaskListPage } from "@/entities/tasks/domain/model/task-list-item";

export type GetBranchTasksParams = { branchName: string; offset: number; limit: number };

export type GetBranchTasksResult = TaskListPage;

export const getBranchTasks = async (
  { branchName, offset, limit }: GetBranchTasksParams,
  options?: TaskRequestOptions
): Promise<GetBranchTasksResult> => {
  const { data } = await getTaskListFromApi({ branchName, offset, limit }, options);

  return toTaskListPage(data.InfrahubTask);
};
