import { Button, ButtonProps } from "@/components/buttons/button-primitive";
import { ALERT_TYPES, Alert } from "@/components/ui/alert";
import { PROPOSED_CHANGES_OBJECT } from "@/config/constants";
import graphqlClient from "@/graphql/graphqlClientApollo";
import { updateObjectWithId } from "@/graphql/mutations/objects/updateObjectWithId";
import { useAuth } from "@/hooks/useAuth";
import { currentBranchAtom } from "@/state/atoms/branches.atom";
import { datetimeAtom } from "@/state/atoms/time.atom";
import { stringifyWithoutQuotes } from "@/utils/string";
import { gql } from "@apollo/client";
import { useAtomValue } from "jotai/index";
import { useState } from "react";
import { toast } from "react-toastify";

interface PcApproveButtonProps extends ButtonProps {
  proposedChangeId: string;
  approvers: Array<any>;
  state: "closed" | "open" | "merged";
}

export const PcApproveButton = ({
  approvers = [],
  proposedChangeId,
  state,
  ...props
}: PcApproveButtonProps) => {
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
      disabled={
        !auth?.permissions?.write ||
        !approverId ||
        !canApprove ||
        state === "closed" ||
        state === "merged"
      }
      {...props}
    >
      Approve
    </Button>
  );
};
