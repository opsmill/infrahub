import type { DeliveryStatus } from "@/entities/repository/domain/model/delivery-state";

export interface DeliveryActions {
  canRetry: boolean;
  canAbandon: boolean;
}

/** Both actions need something pending; a running attempt does not block them, since each waits for it. */
export function getDeliveryActions(status: DeliveryStatus): DeliveryActions {
  const isPending = status !== "none";

  return { canRetry: isPending, canAbandon: isPending };
}
