import { useDeleteObjects } from "@/entities/nodes/object/domain/delete-objects.mutation";
import { NodeObject } from "@/entities/nodes/types";
import { queryClient } from "@/shared/api/rest/client";
import ModalDelete from "@/shared/components/modals/modal-delete";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { pluralize } from "@/shared/utils/string";
import { toast } from "react-toastify";

export interface DeleteObjectModalProps {
  selectedRows: Array<NodeObject>;
  open: boolean;
  setOpen: (b: boolean) => void;
}

export function DeleteObjectsModal({ selectedRows, open, setOpen }: DeleteObjectModalProps) {
  const { mutate, isPending } = useDeleteObjects({
    context: {
      processErrorMessage: (message: string) => {
        const regex = new RegExp(/Cannot delete \w* \'(\w|-)*\'\./g);
        const matches = message.match(regex);

        const messageDisplay = matches?.[0];

        toast(<Alert type={ALERT_TYPES.ERROR} message={messageDisplay} />);

        queryClient.invalidateQueries({
          predicate: (query) => query.queryKey.includes("objects"),
        });
      },
    },
    onSuccess: () => {
      queryClient.invalidateQueries({
        predicate: (query) => query.queryKey.includes("objects"),
      });

      setOpen(false);

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
    <ModalDelete
      title="Delete"
      description={
        <>
          Are you sure you want to delete{" "}
          <strong>{pluralize(selectedRows.length, "object")}</strong> ?
        </>
      }
      open={open}
      setOpen={setOpen}
      onCancel={() => setOpen(false)}
      onDelete={handleRemoveObjects}
      isLoading={isPending}
    />
  );
}
