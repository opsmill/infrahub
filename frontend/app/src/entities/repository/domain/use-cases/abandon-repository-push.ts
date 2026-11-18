import {
  type AbandonRepositoryPushFromApiParams,
  abandonRepositoryPushFromApi,
} from "@/entities/repository/api/abandon-repository-push-from-api";

export type AbandonRepositoryPushParams = AbandonRepositoryPushFromApiParams;

export interface AbandonRepositoryPushResult {
  ok: boolean;
  taskId?: string;
}

export type AbandonRepositoryPush = (
  params: AbandonRepositoryPushParams
) => Promise<AbandonRepositoryPushResult>;

export const abandonRepositoryPush: AbandonRepositoryPush = async (params) => {
  const { data } = await abandonRepositoryPushFromApi(params);
  const result = data?.InfrahubRepositoryDeliveryAbandon;

  if (!result) {
    throw new Error("Cannot abandon the pending pushes.");
  }

  return {
    ok: result.ok ?? false,
    taskId: result.task?.id ?? undefined,
  };
};
