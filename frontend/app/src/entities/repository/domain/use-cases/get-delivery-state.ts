import {
  type GetDeliveryStateFromApiParams,
  getDeliveryStateFromApi,
} from "@/entities/repository/api/get-delivery-state-from-api";
import {
  DeliveryFailureCauseSchema,
  DeliveryQueueSchema,
  type DeliveryState,
  DeliveryStatusSchema,
} from "@/entities/repository/domain/model/delivery-state";

export type GetDeliveryStateParams = GetDeliveryStateFromApiParams;

export type GetDeliveryStateResult = DeliveryState;

export type GetDeliveryState = (params: GetDeliveryStateParams) => Promise<GetDeliveryStateResult>;

export const getDeliveryState: GetDeliveryState = async (params) => {
  const { data } = await getDeliveryStateFromApi(params);
  const repository = data.CoreRepository.edges[0]?.node;

  return {
    // A repository that never pushed has no status yet, which means nothing is pending.
    status:
      DeliveryStatusSchema.nullable().parse(repository?.delivery_status?.value ?? null) ?? "none",
    statusLabel: repository?.delivery_status?.label ?? null,
    statusColor: repository?.delivery_status?.color ?? null,
    cause: DeliveryFailureCauseSchema.nullable().parse(
      repository?.delivery_failure_cause?.value ?? null
    ),
    causeLabel: repository?.delivery_failure_cause?.label ?? null,
    error: repository?.delivery_error?.value ?? null,
    pendingMerges:
      DeliveryQueueSchema.nullable().parse(repository?.delivery_queue?.value ?? null)?.entries ??
      [],
  };
};
