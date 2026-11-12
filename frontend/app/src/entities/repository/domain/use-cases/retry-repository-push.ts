import {
  type RetryRepositoryPushFromApiParams,
  retryRepositoryPushFromApi,
} from "@/entities/repository/api/retry-repository-push-from-api";

export type RetryRepositoryPushParams = RetryRepositoryPushFromApiParams;

export interface RetryRepositoryPushResult {
  ok: boolean;
  taskId?: string;
}

export type RetryRepositoryPush = (
  params: RetryRepositoryPushParams
) => Promise<RetryRepositoryPushResult>;

export const retryRepositoryPush: RetryRepositoryPush = async (params) => {
  const { data } = await retryRepositoryPushFromApi(params);
  const result = data?.InfrahubRepositoryDeliveryRetry;

  if (!result) {
    throw new Error("Cannot start the retry of the pending pushes.");
  }

  return {
    ok: result.ok ?? false,
    taskId: result.task?.id ?? undefined,
  };
};
