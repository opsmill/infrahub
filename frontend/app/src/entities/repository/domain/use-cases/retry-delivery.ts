import {
  type RetryDeliveryFromApiParams,
  retryDeliveryFromApi,
} from "@/entities/repository/api/retry-delivery-from-api";

export type RetryDeliveryParams = RetryDeliveryFromApiParams;

export interface RetryDeliveryResult {
  ok: boolean;
  taskId?: string;
}

export type RetryDelivery = (params: RetryDeliveryParams) => Promise<RetryDeliveryResult>;

export const retryDelivery: RetryDelivery = async (params) => {
  const { data } = await retryDeliveryFromApi(params);
  const result = data?.InfrahubRepositoryDeliveryRetry;

  if (!result) {
    throw new Error("Cannot start the retry of the pending pushes.");
  }

  return {
    ok: result.ok ?? false,
    taskId: result.task?.id ?? undefined,
  };
};
