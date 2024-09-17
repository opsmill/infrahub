import React, { Fragment, useState } from "react";
import ModalDelete from "./modal-delete";
import { deleteObject } from "@/graphql/mutations/objects/deleteObject";
import { toast } from "react-toastify";
import { Alert, ALERT_TYPES } from "../ui/alert";
import graphqlClient from "@/graphql/graphqlClientApollo";
import { ACCOUNT_TOKEN_OBJECT } from "@/config/constants";
import { stringifyWithoutQuotes } from "@/utils/string";
import { gql } from "@apollo/client";
import { useAtomValue } from "jotai";
import { currentBranchAtom } from "@/state/atoms/branches.atom";
import { datetimeAtom } from "@/state/atoms/time.atom";

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
  const branch = useAtomValue(currentBranchAtom);
  const date = useAtomValue(datetimeAtom);

  const handleDeleteObject = async () => {
    if (!rowToDelete?.id) {
      return;
    }

    setIsLoading(true);

    try {
      const mutationString = deleteObject({
        kind:
          rowToDelete.__typename === "AccountTokenNode"
            ? ACCOUNT_TOKEN_OBJECT
            : rowToDelete.__typename,
        data: stringifyWithoutQuotes({
          id: rowToDelete?.id,
        }),
      });

      const mutation = gql`
        ${mutationString}
      `;

      await graphqlClient.mutate({
        mutation,
        context: { branch: branch?.name, date },
      });

      graphqlClient.refetchQueries({ include: [rowToDelete.__typename!] });

      close();

      if (onDelete) onDelete();

      toast(
        <Alert
          type={ALERT_TYPES.SUCCESS}
          message={`Object ${rowToDelete?.display_label} deleted`}
        />
      );
    } catch (error) {
      console.error("Error while deleting object: ", error);
    }

    setIsLoading(false);
  };

  return (
    <ModalDelete
      title="Delete"
      description={
        rowToDelete?.display_label || rowToDelete?.name?.value || rowToDelete?.name ? (
          <>
            Are you sure you want to remove the <i>{label}</i>
            <b className="ml-2">
              &quot;{rowToDelete?.display_label || rowToDelete?.name?.value || rowToDelete?.name}
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
