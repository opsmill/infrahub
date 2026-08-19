import { toast } from "react-toastify";

import { ModalDanger } from "@/shared/components/modals/modal-danger";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { pluralize } from "@/shared/utils/string";

import type { NodeCore } from "@/entities/nodes/object/domain/model/node";
import { useDeleteObjects } from "@/entities/nodes/object/ui/queries/delete-objects.mutation";

export interface DeleteObjectModalProps {
  selectedRows: Array<NodeCore>;
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
}

export function DeleteObjectsModal({ selectedRows, isOpen, onOpenChange }: DeleteObjectModalProps) {
  const { mutate, isPending } = useDeleteObjects({
    context: {
      processErrorMessage: (message: string) => {
        const regex = new RegExp(/Cannot delete \w* '(\w|-)*'\./g);
        const matches = message.match(regex);

        const messageDisplay = matches?.[0];

        toast(<Alert type={ALERT_TYPES.ERROR} message={messageDisplay} />);
      },
    },
    onSuccess: () => {
      onOpenChange(false);

      toast(<Alert type={ALERT_TYPES.SUCCESS} message={"Objects deleted!"} />);
    },
  });

  const handleRemoveObjects = async () => {
    const objects = selectedRows.map(({ id, __typename }) => {
      return { id, kind: __typename };
    });

    mutate({
      objects,
    });
  };

  return (
    <ModalDanger
      title="Delete"
      description={
        <>
          Are you sure you want to delete{" "}
          <strong>{pluralize(selectedRows.length, "object")}</strong> ?
        </>
      }
      isOpen={isOpen}
      onOpenChange={onOpenChange}
      onConfirm={handleRemoveObjects}
      isLoading={isPending}
    />
  );
}
