import {
  type RetryTaskFromApiParams,
  retryTaskFromApi,
} from "@/entities/tasks/api/retry-task-from-api";

export type RetryTaskParams = RetryTaskFromApiParams;

export interface RetryTaskResult {
  ok: boolean;
  taskId?: string;
}

export const retryTask = async (params: RetryTaskParams): Promise<RetryTaskResult> => {
  const { data, errors } = await retryTaskFromApi(params);

  if (errors?.[0]?.message) {
    throw new Error(errors[0].message);
  }

  if (!data?.InfrahubTaskRetry) {
    throw new Error("Failed to retry the task");
  }

  return {
    ok: data.InfrahubTaskRetry.ok ?? false,
    taskId: data.InfrahubTaskRetry.task?.id ?? undefined,
  };
};
