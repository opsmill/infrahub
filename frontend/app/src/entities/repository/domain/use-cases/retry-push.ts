import {
  type RetryPushFromApiParams,
  retryPushFromApi,
} from "@/entities/repository/api/retry-push-from-api";

export type RetryPushParams = RetryPushFromApiParams;

export interface RetryPushResult {
  ok: boolean;
  taskId?: string;
}

export type RetryPush = (params: RetryPushParams) => Promise<RetryPushResult>;

export const retryPush: RetryPush = async (params) => {
  const { data } = await retryPushFromApi(params);
  const result = data?.InfrahubRepositoryDeliveryRetry;

  if (!result) {
    throw new Error("Cannot start the retry of the pending pushes.");
  }

  return {
    ok: result.ok ?? false,
    taskId: result.task?.id ?? undefined,
  };
};
