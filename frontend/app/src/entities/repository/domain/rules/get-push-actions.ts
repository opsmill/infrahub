import type { PushStatus } from "@/entities/repository/domain/model/repository-push-state";

export interface PushActions {
  canRetry: boolean;
  canAbandon: boolean;
}

/** Both actions need something pending; a running attempt does not block them, since each waits for it. */
export function getPushActions(status: PushStatus): PushActions {
  const isPending = status !== "none";

  return { canRetry: isPending, canAbandon: isPending };
}
