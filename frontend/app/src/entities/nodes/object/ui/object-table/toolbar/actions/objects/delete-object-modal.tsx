import { useDeleteObject } from "@/entities/nodes/object/domain/delete-object.mutation";
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
  const { mutate, isPending } = useDeleteObject();

  const handleRemoveObjects = async () => {
    await Promise.all(
      selectedRows.map(({ id, __typename }) => {
        return mutate({
          objectId: id,
          objectKind: __typename,
        });
      })
    );

    await graphqlClient.reFetchObservableQueries();

    setOpen(false);

    toast(<Alert type={ALERT_TYPES.SUCCESS} message={"Objects deleted!"} />);
  };

  return (
    <ModalDelete
      title="Delete"
      description={
        <p>
          Are you sure you want to delete{" "}
          <strong>{pluralize(selectedRows.length, "object")}</strong> ?
        </p>
      }
      open={open}
      setOpen={setOpen}
      onCancel={() => setOpen(false)}
      onDelete={handleRemoveObjects}
      isLoading={isPending}
    />
  );
}
