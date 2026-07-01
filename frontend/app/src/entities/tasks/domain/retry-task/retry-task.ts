import {
  type RetryTaskFromApiParams,
  retryTaskFromApi,
} from "@/entities/tasks/api/retry-task-from-api";

export type RetryTaskParams = RetryTaskFromApiParams;

export const retryTask = async (params: RetryTaskParams): Promise<string | undefined> => {
  const { data, errors } = await retryTaskFromApi(params);

  if (errors?.length) {
    throw new Error(errors.map((error) => error.message).join("; "));
  }

  return data?.InfrahubTaskRetry?.task?.id ?? undefined;
};
