import { ToggleButtons } from "@/components/buttons/toggle-buttons";
import { ALERT_TYPES, Alert } from "@/components/ui/alert";
import graphqlClient from "@/graphql/graphqlClientApollo";
import { resolveConflict } from "@/graphql/mutations/diff/resolveConflict";
import { currentBranchAtom } from "@/state/atoms/branches.atom";
import { datetimeAtom } from "@/state/atoms/time.atom";
import { gql } from "@apollo/client";
import { useAtomValue } from "jotai/index";
import { useState } from "react";
import { toast } from "react-toastify";

export const Conflict = ({ conflict }: any) => {
  const currentBranch = useAtomValue(currentBranchAtom);
  const date = useAtomValue(datetimeAtom);
  const [isLoading, setIsLoading] = useState(false);

  const handleAccept = async (conflictValue: string) => {
    try {
      setIsLoading(true);

      const newValue = conflictValue === conflict.selected_branch ? null : conflictValue;

      const mutation = gql`
        ${resolveConflict}
      `;

      await graphqlClient.mutate({
        mutation,
        variables: {
          uuid: conflict.uuid,
          conflict_selection: newValue,
        },
        context: {
          branch: currentBranch?.name,
          date,
        },
      });

      toast(<Alert type={ALERT_TYPES.SUCCESS} message="Conflict marked as resovled" />);

      setIsLoading(false);
    } catch (error) {
      console.error("Error while updateing the conflict: ", error);
      setIsLoading(false);
    }
  };

  const tabs = [
    {
      label: "Base",
      isActive: conflict.selected_branch === "Base",
      onClick: () => handleAccept("Base"),
    },
    {
      label: "Branch",
      isActive: conflict.selected_branch === "Branch",
      onClick: () => handleAccept("Branch"),
    },
  ];

  return (
    <div className="flex items-center justify-end p-2">
      <span className="mr-1">Accept:</span>
      <ToggleButtons tabs={tabs} isLoading={isLoading} />
    </div>
  );
};
