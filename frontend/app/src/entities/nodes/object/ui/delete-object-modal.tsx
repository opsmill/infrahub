import { toast } from "react-toastify";

import ModalDelete from "@/shared/components/modals/modal-delete";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";

import { useDeleteObjectMutation } from "@/entities/nodes/object/domain/delete-object.mutation";

export interface DeleteObjectModalProps {
  objectId: string;
  objectKind: string;
  objectLabel: string;
  open: boolean;
  setOpen: (b: boolean) => void;
  toastMessage?: string;
}

export function DeleteObjectModal({
  objectKind,
  objectLabel,
  objectId,
  open,
  setOpen,
  toastMessage,
}: DeleteObjectModalProps) {
  const { mutate, isPending } = useDeleteObjectMutation();

  return (
    <ModalDelete
      title="Delete"
      description={
        <>
          Are you sure you want to remove <span className="mx-1 font-semibold">{objectLabel}</span>?
        </>
      }
      open={open}
      setOpen={setOpen}
      onCancel={() => setOpen(false)}
      onDelete={() =>
        mutate(
          { objectKind, objectId },
          {
            onSuccess: () => {
              setOpen(false);
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
