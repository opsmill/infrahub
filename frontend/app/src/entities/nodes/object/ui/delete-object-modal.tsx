import { toast } from "react-toastify";

import { ModalDanger } from "@/shared/components/modals/modal-danger";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";

import { useDeleteObjectMutation } from "@/entities/nodes/object/ui/queries/delete-object.mutation";

export interface DeleteObjectModalProps {
  objectId: string;
  objectKind: string;
  objectLabel: string;
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  toastMessage?: string;
}

export function DeleteObjectModal({
  objectKind,
  objectLabel,
  objectId,
  isOpen,
  onOpenChange,
  toastMessage,
}: DeleteObjectModalProps) {
  const { mutate, isPending } = useDeleteObjectMutation();

  return (
    <ModalDanger
      title="Delete"
      description={
        <>
          Are you sure you want to remove <span className="mx-1 font-semibold">{objectLabel}</span>?
        </>
      }
      isOpen={isOpen}
      onOpenChange={onOpenChange}
      onConfirm={() =>
        mutate(
          { objectKind, objectId },
          {
            onSuccess: () => {
              onOpenChange(false);
              toast(
                <Alert
                  type={ALERT_TYPES.SUCCESS}
                  message={toastMessage ?? `Object ${objectLabel} deleted`}
                />
              );
            },
          }
        )
      }
      isLoading={isPending}
    />
  );
}
