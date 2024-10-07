import { Button, ButtonProps } from "@/components/buttons/button-primitive";
import { updateObjectWithId } from "@/graphql/mutations/objects/updateObjectWithId";
import { PROPOSED_CHANGES_OBJECT } from "@/config/constants";
import { stringifyWithoutQuotes } from "@/utils/string";
import { gql } from "@apollo/client";
import graphqlClient from "@/graphql/graphqlClientApollo";
import { toast } from "react-toastify";
import { Alert, ALERT_TYPES } from "@/components/ui/alert";
import React, { useState } from "react";
import { useAtomValue } from "jotai/index";
import { currentBranchAtom } from "@/state/atoms/branches.atom";
import { datetimeAtom } from "@/state/atoms/time.atom";
import { useAuth } from "@/hooks/useAuth";

interface PcMergeButtonProps extends ButtonProps {
  proposedChangeId: string;
  approvers: Array<any>;
}

export const PcApproveButton = ({
  approvers = [],
  proposedChangeId,
  ...props
}: PcMergeButtonProps) => {
  const branch = useAtomValue(currentBranchAtom);
  const date = useAtomValue(datetimeAtom);
  const auth = useAuth();
  const [isLoadingApprove, setIsLoadingApprove] = useState(false);

  const approverId = auth?.data?.sub;
  const canApprove = !approvers?.map((a: any) => a.id).includes(approverId);

  const handleApprove = async () => {
    if (!approverId) {
      return;
    }

    setIsLoadingApprove(true);

    const oldApproversId = approvers.map((a: any) => a.id);
    const newApproversId = Array.from(new Set([...oldApproversId, approverId]));
    const newApprovers = newApproversId.map((id: string) => ({ id }));

    const data = {
      approved_by: newApprovers,
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

      await graphqlClient.reFetchObservableQueries();
      toast(<Alert type={ALERT_TYPES.SUCCESS} message="Proposed change approved" />);

      setIsLoadingApprove(false);

      return;
    } catch (e) {
      console.error("Something went wrong while updating the object:", e);

      return;
    }
  };

  return (
    <Button
      variant="outline"
      onClick={handleApprove}
      isLoading={isLoadingApprove}
      disabled={!auth?.permissions?.write || !approverId || !canApprove}
      {...props}
    >
      Approve
    </Button>
  );
};
