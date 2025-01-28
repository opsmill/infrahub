import { useDeleteObject } from "@/entities/nodes/object/domain/delete-object.mutation";
import ModalDelete from "@/shared/components/modals/modal-delete";

export interface DeleteObjectModalProps {
  objectId: string;
  objectKind: string;
  objectLabel: string;
  open: boolean;
  setOpen: (b: boolean) => void;
}

export function DeleteObjectModal({
  objectKind,
  objectLabel,
  objectId,
  open,
  setOpen,
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
      onDelete={() => mutate({ objectKind, objectId }, { onSuccess: () => setOpen(false) })}
      isLoading={isPending}
    />
  );
}
