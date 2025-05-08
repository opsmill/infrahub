import { useDeleteObjects } from "@/entities/nodes/object/domain/delete-objects.mutation";
import { NodeObject } from "@/entities/nodes/types";
import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
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

        toast(<Alert type={ALERT_TYPES.ERROR} message={matches[0]} />);

        graphqlClient.reFetchObservableQueries();
      },
    },
    onSuccess: () => {
      graphqlClient.reFetchObservableQueries();

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
