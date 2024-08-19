import { ToggleButtons } from "@/components/buttons/toggle-buttons";
import { ALERT_TYPES, Alert } from "@/components/ui/alert";
import { DATA_CHECK_OBJECT } from "@/config/constants";
import graphqlClient from "@/graphql/graphqlClientApollo";
import { updateObjectWithId } from "@/graphql/mutations/objects/updateObjectWithId";
import { currentBranchAtom } from "@/state/atoms/branches.atom";
import { datetimeAtom } from "@/state/atoms/time.atom";
import { stringifyWithoutQuotes } from "@/utils/string";
import { gql } from "@apollo/client";
import { useAtomValue } from "jotai/index";
import { useState } from "react";
import { toast } from "react-toastify";

export const Conflict = ({ conflict, id }: any) => {
  const currentBranch = useAtomValue(currentBranchAtom);
  const date = useAtomValue(datetimeAtom);
  const [isLoading, setIsLoading] = useState(false);

  const handleAccept = async (conflictValue: string) => {
    try {
      setIsLoading(true);

      const newValue = conflictValue === conflict.selected_branch ? null : conflictValue;

      const newData = {
        id,
        keep_branch: {
          value: newValue,
        },
      };

      const mustationString = updateObjectWithId({
        kind: DATA_CHECK_OBJECT,
        data: stringifyWithoutQuotes(newData),
      });

      const mutation = gql`
        ${mustationString}
      `;

      await graphqlClient.mutate({
        mutation,
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
      label: "target",
      isActive: conflict.selected_branch === "target",
      onClick: () => handleAccept("target"),
    },
    {
      label: "source",
      isActive: conflict.selected_branch === "source",
      onClick: () => handleAccept("source"),
    },
  ];

  return (
    <div className="flex items-center justify-end p-2">
      <span className="mr-1">Accept:</span>
      <ToggleButtons tabs={tabs} isLoading={isLoading} />
    </div>
  );
};
