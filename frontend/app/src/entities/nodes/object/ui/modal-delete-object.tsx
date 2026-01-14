import { useState } from "react";
import { toast } from "react-toastify";

import { ModalDelete } from "@/shared/components/aria/modal-delete";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { ACCOUNT_TOKEN_OBJECT } from "@/shared/config/constants";

import { useDeleteObjectMutation } from "@/entities/nodes/object/domain/delete-object.mutation";
import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";

interface iProps {
  label?: string | null;
  rowToDelete: any;
  isLoading?: boolean;
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  onDelete?: () => void;
}

export default function ModalDeleteObject({
  label,
  rowToDelete,
  isOpen,
  onOpenChange,
  onDelete,
}: iProps) {
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const deleteObject = useDeleteObjectMutation();

  const objectDisplay =
    (rowToDelete && "__typename" in rowToDelete && "id" in rowToDelete
      ? getNodeLabel(rowToDelete)
      : null) ||
    rowToDelete?.display_label?.value ||
    rowToDelete?.display_label ||
    rowToDelete?.name?.value ||
    rowToDelete?.name;

  const handleDeleteObject = async () => {
    if (!rowToDelete?.id) {
      return;
    }

    setIsLoading(true);

    await deleteObject.mutateAsync(
      {
        objectKind:
          rowToDelete.__typename === "AccountTokenNode"
            ? ACCOUNT_TOKEN_OBJECT
            : rowToDelete.__typename,
        objectId: rowToDelete?.id,
      },
      {
        onSuccess: async () => {
          if (onDelete) await onDelete();

          onOpenChange(false);

          toast(<Alert type={ALERT_TYPES.SUCCESS} message={`Object ${objectDisplay} deleted`} />);
        },
        onError: (error) => {
          console.error("Error while deleting object: ", error);
        },
      }
    );
    setIsLoading(false);
  };

  return (
    <ModalDelete
      title="Delete"
      description={
        objectDisplay ? (
          <>
            Are you sure you want to remove the <i>{label}</i>
            <b className="ml-2">
              &quot;{objectDisplay}
              &quot;
            </b>
            ?
          </>
        ) : (
          <>
            Are you sure you want to remove this <i>{label}</i>?
          </>
        )
      }
      onDelete={handleDeleteObject}
      isOpen={isOpen}
      onOpenChange={onOpenChange}
      isLoading={isLoading}
    />
  );
}
