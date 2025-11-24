import { useState } from "react";
import { useParams } from "react-router";
import { toast } from "react-toastify";

import { ACCOUNT_TOKEN_OBJECT } from "@/config/constants";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

import { useDeleteObjectMutation } from "@/entities/nodes/object/domain/delete-object.mutation";
import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";

import { ALERT_TYPES, Alert } from "../ui/alert";
import ModalDelete from "./modal-delete";

interface iProps {
  label?: string | null;
  rowToDelete: any;
  isLoading?: boolean;
  open: boolean;
  close: () => void;
  onDelete?: () => void;
}

export default function ModalDeleteObject({ label, rowToDelete, open, close, onDelete }: iProps) {
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const { objectKind } = useParams();
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
          if (objectKind) await graphqlClient.refetchQueries({ include: [objectKind!] });

          if (onDelete) await onDelete();

          close();

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
      onCancel={close}
      onDelete={handleDeleteObject}
      open={!!open}
      setOpen={close}
      isLoading={isLoading}
    />
  );
}
