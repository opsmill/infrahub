import { useDeleteObject } from "@/entities/nodes/object/domain/delete-object.mutation";
import ModalDelete from "@/shared/components/modals/modal-delete";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { toast } from "react-toastify";

export interface DeleteObjectModalProps {
  objectId: string;
  objectKind: string;
  objectLabel: string;
  open: boolean;
  setOpen: (b: boolean) => void;
  alertMessage?: string;
}

export function DeleteObjectModal({
  objectKind,
  objectLabel,
  objectId,
  open,
  setOpen,
  alertMessage,
}: DeleteObjectModalProps) {
  const { mutate, isPending } = useDeleteObject();

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
                  message={alertMessage ?? `Object ${objectLabel} deleted`}
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
