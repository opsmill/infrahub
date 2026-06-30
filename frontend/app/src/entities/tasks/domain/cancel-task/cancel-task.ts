import {
  type CancelTaskFromApiParams,
  cancelTaskFromApi,
} from "@/entities/tasks/api/cancel-task-from-api";
import {
  mapTaskActionResult,
  type TaskActionResult,
} from "@/entities/tasks/domain/task-action-result";

export type CancelTaskParams = CancelTaskFromApiParams;
export type CancelTaskResult = TaskActionResult;

export const cancelTask = async (params: CancelTaskParams): Promise<CancelTaskResult> => {
  const { data, errors } = await cancelTaskFromApi(params);
  return mapTaskActionResult(data?.InfrahubTaskCancel, errors, "Failed to cancel the task");
};
