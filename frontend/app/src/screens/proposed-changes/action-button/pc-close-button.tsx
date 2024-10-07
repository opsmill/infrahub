import { Button, ButtonProps } from "@/components/buttons/button-primitive";
import React, { useState } from "react";
import { updateObjectWithId } from "@/graphql/mutations/objects/updateObjectWithId";
import { PROPOSED_CHANGES_OBJECT } from "@/config/constants";
import { stringifyWithoutQuotes } from "@/utils/string";
import { gql } from "@apollo/client";
import graphqlClient from "@/graphql/graphqlClientApollo";
import { toast } from "react-toastify";
import { Alert, ALERT_TYPES } from "@/components/ui/alert";
import { useAtomValue } from "jotai/index";
import { currentBranchAtom } from "@/state/atoms/branches.atom";
import { datetimeAtom } from "@/state/atoms/time.atom";
import { usePermission } from "@/hooks/usePermission";

interface PcCloseButtonProps extends ButtonProps {
  proposedChangeId: string;
  state: "closed" | "open" | "merged";
}

export const PcCloseButton = ({ proposedChangeId, state, ...props }: PcCloseButtonProps) => {
  const [isLoadingClose, setIsLoadingClose] = useState(false);
  const branch = useAtomValue(currentBranchAtom);
  const date = useAtomValue(datetimeAtom);
  const permission = usePermission();

  const handleClose = async () => {
    setIsLoadingClose(true);

    const newState = state === "closed" ? "open" : "closed";

    const data = {
      state: {
        value: newState,
      },
    };

    try {
      const mutationString = updateObjectWithId({
        kind: PROPOSED_CHANGES_OBJECT,
        data: stringifyWithoutQuotes({
          id: proposedChangeId,
          ...data,
        }),
      });

      const mutation = gql`
        ${mutationString}
      `;

      await graphqlClient.mutate({
        mutation,
        context: { branch: branch?.name, date },
      });

      toast(
        <Alert
          type={ALERT_TYPES.SUCCESS}
          message={`Proposed change ${state === "closed" ? "opened" : "closed"}`}
        />
      );

      await graphqlClient.reFetchObservableQueries();
      setIsLoadingClose(false);

      return;
    } catch (e) {
      console.error("Something went wrong while updating the object:", e);

      setIsLoadingClose(false);

      return;
    }
  };

  return (
    <Button
      variant="danger"
      onClick={handleClose}
      isLoading={isLoadingClose}
      disabled={!permission.write.allow || state === "merged"}
      {...props}
    >
      {state === "closed" ? "Re-open" : "Close"}
    </Button>
  );
};
