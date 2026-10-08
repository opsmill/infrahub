import {
  type AbandonDeliveryFromApiParams,
  abandonDeliveryFromApi,
} from "@/entities/repository/api/abandon-delivery-from-api";

export type AbandonDeliveryParams = AbandonDeliveryFromApiParams;

export interface AbandonDeliveryResult {
  ok: boolean;
  taskId?: string;
}

export type AbandonDelivery = (params: AbandonDeliveryParams) => Promise<AbandonDeliveryResult>;

export const abandonDelivery: AbandonDelivery = async (params) => {
  const { data } = await abandonDeliveryFromApi(params);
  const result = data?.InfrahubRepositoryDeliveryAbandon;

  if (!result) {
    throw new Error("Cannot start the abandonment of the pending pushes.");
  }

  return {
    ok: result.ok ?? false,
    taskId: result.task?.id ?? undefined,
  };
};
