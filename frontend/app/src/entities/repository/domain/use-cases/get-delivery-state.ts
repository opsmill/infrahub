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

  const queue = DeliveryQueueSchema.nullish().safeParse(repository?.delivery_queue?.value);
  if (!queue.success) {
    throw new Error("Cannot read the pending pushes of this repository.");
  }

  // A value this page does not know still shows with the backend's label, and still asks the user to act.
  const status =
    DeliveryStatusSchema.nullish()
      .catch("action-required")
      .parse(repository?.delivery_status?.value) ?? "none";
  const cause =
    DeliveryFailureCauseSchema.nullish()
      .catch("unclassified")
      .parse(repository?.delivery_failure_cause?.value) ?? null;

  return {
    status,
    statusLabel: repository?.delivery_status?.label ?? status,
    statusColor: repository?.delivery_status?.color ?? null,
    cause,
    causeLabel: repository?.delivery_failure_cause?.label ?? cause,
    error: repository?.delivery_error?.value ?? null,
    pendingMerges: queue.data?.entries ?? [],
  };
};
