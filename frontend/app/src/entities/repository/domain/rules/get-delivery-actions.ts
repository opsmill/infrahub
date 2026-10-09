import type { DeliveryStatus } from "@/entities/repository/domain/model/delivery-state";

export interface DeliveryActions {
  canRetry: boolean;
  canAbandon: boolean;
}

/**
 * Both actions need something pending; a running attempt does not block them, since each waits for it.
 * A state that cannot be read still allows a retry, which the backend refuses when nothing is pending,
 * but no abandonment, which names the queue version that the user read.
 */
export function getDeliveryActions(status: DeliveryStatus | "unreadable"): DeliveryActions {
  if (status === "unreadable") {
    return { canRetry: true, canAbandon: false };
  }

  const isPending = status !== "none";

  return { canRetry: isPending, canAbandon: isPending };
}
