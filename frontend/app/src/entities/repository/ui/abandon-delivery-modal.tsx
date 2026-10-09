import { toast } from "react-toastify";

import { queryClient } from "@/shared/api/rest/client";
import { ModalDanger } from "@/shared/components/modals/modal-danger";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";

import { objectQueryKeys } from "@/entities/nodes/object/ui/queries/object.query-keys";
import type { DeliveryState } from "@/entities/repository/domain/model/delivery-state";
import { PendingMergeList } from "@/entities/repository/ui/pending-merge-list";
import { useAbandonDeliveryMutation } from "@/entities/repository/ui/queries/abandon-delivery.mutation";
import { DELIVERY_TEXTS } from "@/entities/repository/ui/repository-delivery-texts";
import { toastTaskStarted } from "@/entities/repository/ui/toast-task-started";

interface AbandonDeliveryModalProps {
  repositoryId: string;
  /** The push state the user read: the backend refuses the abandonment if its pending merges changed since. */
  deliveryState: DeliveryState;
  isOpen: boolean;
  onOpenChange: (isOpen: boolean) => void;
}

export function AbandonDeliveryModal({
  repositoryId,
  deliveryState,
  isOpen,
  onOpenChange,
}: AbandonDeliveryModalProps) {
  const { mutate: abandonDelivery, isPending } = useAbandonDeliveryMutation({
    onSuccess: (result) => {
      toastTaskStarted(DELIVERY_TEXTS.abandonStarted, result.taskId);
    },
    onError: (error) => {
      toast(
        <Alert
          type={ALERT_TYPES.ERROR}
          message={`${DELIVERY_TEXTS.abandonFailed} ${error.message}`}
        />
      );
    },
    // After a refusal the list shown is out of date, so the user reopens the modal to read the new one.
    onSettled: async () => {
      onOpenChange(false);
      await queryClient.invalidateQueries({ queryKey: objectQueryKeys.all });
    },
  });

  return (
    <ModalDanger
      title={DELIVERY_TEXTS.abandon}
      description={
        <div className="flex flex-col gap-2">
          <p>{DELIVERY_TEXTS.abandonMerges}</p>
          <PendingMergeList merges={deliveryState.pendingMerges} />
          <p>{DELIVERY_TEXTS.abandonKeepsRemote}</p>
          <p>{DELIVERY_TEXTS.abandonKeepsObjects}</p>
        </div>
      }
      confirmLabel={DELIVERY_TEXTS.abandonConfirm}
      isOpen={isOpen}
      onOpenChange={onOpenChange}
      isLoading={isPending}
      onConfirm={() => abandonDelivery({ repositoryId, queueVersion: deliveryState.queueVersion })}
    />
  );
}
