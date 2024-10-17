import { Button, ButtonProps } from "@/components/buttons/button-primitive";
import { ALERT_TYPES, Alert } from "@/components/ui/alert";
import { PROPOSED_CHANGES_OBJECT } from "@/config/constants";
import graphqlClient from "@/graphql/graphqlClientApollo";
import { updateObjectWithId } from "@/graphql/mutations/objects/updateObjectWithId";
import { currentBranchAtom } from "@/state/atoms/branches.atom";
import { datetimeAtom } from "@/state/atoms/time.atom";
import { stringifyWithoutQuotes } from "@/utils/string";
import { gql } from "@apollo/client";
import { useAtomValue } from "jotai/index";
import { useState } from "react";
import { toast } from "react-toastify";

interface PcMergeButtonProps extends ButtonProps {
  proposedChangeId: string;
  state: "closed" | "open" | "merged";
  sourceBranch?: string;
}

export const PcMergeButton = ({
  sourceBranch,
  proposedChangeId,
  state,
  disabled,
  ...props
}: PcMergeButtonProps) => {
  const [isLoadingMerge, setIsLoadingMerge] = useState(false);
  const branch = useAtomValue(currentBranchAtom);
  const date = useAtomValue(datetimeAtom);

  const handleMerge = async () => {
    if (!sourceBranch) return;

    try {
      setIsLoadingMerge(true);

      const stateData = {
        state: {
          value: "merged",
        },
      };

      const stateMutationString = updateObjectWithId({
        kind: PROPOSED_CHANGES_OBJECT,
        data: stringifyWithoutQuotes({
          id: proposedChangeId,
          ...stateData,
        }),
      });

      const stateMutation = gql`
        ${stateMutationString}
      `;

      await graphqlClient.mutate({
        mutation: stateMutation,
        context: { branch: branch?.name, date },
      });

      await graphqlClient.reFetchObservableQueries();
      toast(<Alert type={ALERT_TYPES.SUCCESS} message={"Proposed changes merged successfully!"} />);
    } catch (error: any) {
      toast(
        <Alert
          type={ALERT_TYPES.SUCCESS}
          message={"An error occurred while merging the proposed changes"}
        />
      );
    }

    setIsLoadingMerge(false);
  };

  return (
    <Button
      variant="active"
      onClick={handleMerge}
      isLoading={isLoadingMerge}
      disabled={disabled || state === "closed" || state === "merged"}
      {...props}
    >
      Merge
    </Button>
  );
};
