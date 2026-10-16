import {
  type AbandonPushFromApiParams,
  abandonPushFromApi,
} from "@/entities/repository/api/abandon-push-from-api";

export type AbandonPushParams = AbandonPushFromApiParams;

export interface AbandonPushResult {
  ok: boolean;
  taskId?: string;
}

export type AbandonPush = (params: AbandonPushParams) => Promise<AbandonPushResult>;

export const abandonPush: AbandonPush = async (params) => {
  const { data } = await abandonPushFromApi(params);
  const result = data?.InfrahubRepositoryDeliveryAbandon;

  if (!result) {
    throw new Error("Cannot start the abandonment of the pending pushes.");
  }

  return {
    ok: result.ok ?? false,
    taskId: result.task?.id ?? undefined,
  };
};
