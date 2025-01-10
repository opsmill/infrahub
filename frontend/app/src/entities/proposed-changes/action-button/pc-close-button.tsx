import { PROPOSED_CHANGES_OBJECT } from "@/config/constants";
import { currentBranchAtom } from "@/entities/branches/branches.atom";
import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import { updateObjectWithId } from "@/shared/api/graphql/mutations/objects/updateObjectWithId";
import { Button, ButtonProps } from "@/shared/components/buttons/button-primitive";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { datetimeAtom } from "@/shared/stores/time.atom";
import { stringifyWithoutQuotes } from "@/shared/utils/string";
import { gql } from "@apollo/client";
import { useAtomValue } from "jotai/index";
import { useState } from "react";
import { toast } from "react-toastify";

interface PcCloseButtonProps extends ButtonProps {
  proposedChangeId: string;
  state: "closed" | "open" | "merged";
}

export const PcCloseButton = ({
  proposedChangeId,
  state,
  disabled,
  ...props
}: PcCloseButtonProps) => {
  const [isLoadingClose, setIsLoadingClose] = useState(false);
  const branch = useAtomValue(currentBranchAtom);
  const date = useAtomValue(datetimeAtom);

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
      disabled={disabled || state === "merged"}
      {...props}
    >
      {state === "closed" ? "Re-open" : "Close"}
    </Button>
  );
};
