import { getRemoteCheckTaskFromApi } from "@/entities/repository/api/get-remote-check-task-from-api";
import { TASK_ONGOING_STATES } from "@/entities/tasks/domain/model/task";

export interface GetRemoteCheckTaskParams {
  taskId: string;
}

export interface GetRemoteCheckTaskResult {
  isOngoing: boolean;
}

export type GetRemoteCheckTask = (
  params: GetRemoteCheckTaskParams
) => Promise<GetRemoteCheckTaskResult>;

export const getRemoteCheckTask: GetRemoteCheckTask = async ({ taskId }) => {
  const { data } = await getRemoteCheckTaskFromApi({ taskId });
  const state = data.InfrahubTask.edges[0]?.node?.state;

  // The run exists before the mutation returns its id, so a task that is not listed was deleted.
  return { isOngoing: TASK_ONGOING_STATES.some((ongoing) => ongoing === state) };
};
