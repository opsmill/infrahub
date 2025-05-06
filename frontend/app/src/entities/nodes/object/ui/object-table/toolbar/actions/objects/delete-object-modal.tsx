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
  const { mutate, isPending } = useDeleteObjects();

  const handleRemoveObjects = async () => {
    const objectIds = selectedRows.map(({ id }) => {
      return id;
    });

    const objectKind = selectedRows[0]?.__typename;

    const res = await mutate({
      objectIds,
      objectKind,
    });
    console.log("res: ", res);

    await graphqlClient.reFetchObservableQueries();

    setOpen(false);

    toast(<Alert type={ALERT_TYPES.SUCCESS} message={"Objects deleted!"} />);
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
