import { Checkbox } from "@/components/inputs/checkbox";
import { ALERT_TYPES, Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import graphqlClient from "@/graphql/graphqlClientApollo";
import { resolveConflict } from "@/graphql/mutations/diff/resolveConflict";
import { useAuth } from "@/hooks/useAuth";
import LoadingScreen from "@/screens/loading-screen/loading-screen";
import { currentBranchAtom } from "@/state/atoms/branches.atom";
import { proposedChangedState } from "@/state/atoms/proposedChanges.atom";
import { datetimeAtom } from "@/state/atoms/time.atom";
import { gql } from "@apollo/client";
import { Icon } from "@iconify-icon/react";
import { useAtomValue } from "jotai/index";
import { useState } from "react";
import { toast } from "react-toastify";

export const Conflict = ({ conflict }: any) => {
  const currentBranch = useAtomValue(currentBranchAtom);
  const date = useAtomValue(datetimeAtom);
  const [isLoading, setIsLoading] = useState(false);
  const proposedChangesDetails = useAtomValue(proposedChangedState);

  const { isAuthenticated } = useAuth();

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
          id: conflict.uuid,
          selection: newValue,
        },
        context: {
          branch: currentBranch?.name,
          date,
        },
      });

      await graphqlClient.refetchQueries({ include: ["GET_PROPOSED_CHANGES_DIFF_TREE"] });

      const message = newValue ? "Conflict marked as resolved" : "Conflict marked as not resolved";

      toast(<Alert type={ALERT_TYPES.SUCCESS} message={message} />);

      setIsLoading(false);
    } catch (error) {
      console.error("Error while updateing the conflict: ", error);
      setIsLoading(false);
    }
  };

  return (
    <div className="flex items-center justify-end gap-2 p-2">
      {isLoading && <LoadingScreen hideText size={16} />}

      <span className="text-xs">Choose the branch to resolve the conflict:</span>

      <div className="flex gap-2">
        <div className="flex items-center gap-2">
          <Checkbox
            id={"base"}
            disabled={isLoading || !isAuthenticated}
            checked={conflict.selected_branch === "BASE_BRANCH"}
            onChange={() => handleAccept("BASE_BRANCH")}
          />
          <label
            htmlFor={"base"}
            className={
              conflict.selected_branch === "BASE_BRANCH" ? "cursor-default" : "cursor-pointer"
            }
          >
            <Badge variant="green">
              <Icon icon="mdi:layers-triple" className="mr-1" />
              {proposedChangesDetails.destination_branch?.value}
            </Badge>
          </label>
        </div>

        <div className="flex items-center gap-2">
          <Checkbox
            id={"diff"}
            disabled={isLoading || !isAuthenticated}
            checked={conflict.selected_branch === "DIFF_BRANCH"}
            onChange={() => handleAccept("DIFF_BRANCH")}
          />
          <label
            htmlFor={"diff"}
            className={
              conflict.selected_branch === "DIFF_BRANCH" ? "cursor-default" : "cursor-pointer"
            }
          >
            <Badge variant="blue">
              <Icon icon="mdi:layers-triple" className="mr-1" />
              {proposedChangesDetails.source_branch?.value}
            </Badge>
          </label>
        </div>
      </div>
    </div>
  );
};
