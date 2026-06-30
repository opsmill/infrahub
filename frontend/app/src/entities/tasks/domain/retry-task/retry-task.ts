import {
  type RetryTaskFromApiParams,
  retryTaskFromApi,
} from "@/entities/tasks/api/retry-task-from-api";
import {
  mapTaskActionResult,
  type TaskActionResult,
} from "@/entities/tasks/domain/task-action-result";

export type RetryTaskParams = RetryTaskFromApiParams;
export type RetryTaskResult = TaskActionResult;

export const retryTask = async (params: RetryTaskParams): Promise<RetryTaskResult> => {
  const { data, errors } = await retryTaskFromApi(params);
  return mapTaskActionResult(data?.InfrahubTaskRetry, errors, "Failed to retry the task");
};
