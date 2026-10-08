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
  const { data } = await getRemoteCheckTaskFromApi({ taskId, state: TASK_ONGOING_STATES });

  return { isOngoing: data.InfrahubTask.count > 0 };
};
