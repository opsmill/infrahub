import { toast } from "react-toastify";

import { queryClient } from "@/shared/api/rest/client";
import { ModalDelete } from "@/shared/components/aria/modal-delete";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { pluralize } from "@/shared/utils/string";

import { useDeleteObjects } from "@/entities/nodes/object/domain/delete-objects.mutation";
import { objectQueryKeys } from "@/entities/nodes/object/domain/object.query-keys";
import type { NodeCore } from "@/entities/nodes/types";

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
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: objectQueryKeys.all });
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
    <ModalDelete
      title="Delete"
      description={
        <>
          Are you sure you want to delete{" "}
          <strong>{pluralize(selectedRows.length, "object")}</strong> ?
        </>
      }
      isOpen={isOpen}
      onOpenChange={onOpenChange}
      onDelete={handleRemoveObjects}
      isLoading={isPending}
    />
  );
}
