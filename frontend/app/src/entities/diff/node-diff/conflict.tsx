import { Icon } from "@iconify-icon/react";
import { useAtomValue } from "jotai";
import { toast } from "react-toastify";

import type { ConflictSelection } from "@/shared/api/graphql/generated/graphql";
import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import { queryClient } from "@/shared/api/rest/client";
import { Checkbox } from "@/shared/components/inputs/checkbox";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { Badge } from "@/shared/components/ui/badge";
import { Spinner } from "@/shared/components/ui/spinner";

import { useAuth } from "@/entities/authentication/ui/useAuth";
import { treeQueryKeys } from "@/entities/diff/domain/diff.query-keys";
import { useResolveConflictMutation } from "@/entities/diff/domain/resolve-conflict.mutation";
import { proposedChangedState } from "@/entities/proposed-changes/stores/proposedChanges.atom";

interface ConflictData {
  id: string;
  selectedBranch?: ConflictSelection;
}

export const Conflict = ({ id, selectedBranch }: ConflictData) => {
  const proposedChangesDetails = useAtomValue(proposedChangedState);
  const { mutate, isPending } = useResolveConflictMutation();

  const { isAuthenticated } = useAuth();

  const handleAccept = (conflictValue: ConflictSelection) => {
    const newValue = conflictValue === selectedBranch ? null : conflictValue;

    mutate(
      {
        id,
        selection: newValue,
      },
      {
        onSuccess: async () => {
          await queryClient.invalidateQueries({ queryKey: treeQueryKeys.all });
          await graphqlClient.refetchQueries({
            include: ["TASK_DETAILS_CHECK"],
          });

          const message = newValue
            ? "Conflict marked as resolved"
            : "Conflict marked as not resolved";

          toast(<Alert type={ALERT_TYPES.SUCCESS} message={message} />);
        },
        onError: ({ message }) => {
          toast(<Alert type={ALERT_TYPES.ERROR} message={message} />);
        },
      }
    );
  };

  return (
    <div className="flex items-center justify-end gap-2 p-2">
      {isPending && <Spinner />}

      <span className="text-xs">Choose the branch to resolve the conflict:</span>

      <div className="flex gap-2">
        <div className="flex items-center gap-2">
          <Checkbox
            id={"base"}
            disabled={isPending || !isAuthenticated}
            checked={selectedBranch === "BASE_BRANCH"}
            onChange={() => handleAccept("BASE_BRANCH")}
          />
          <label
            htmlFor={"base"}
            className={selectedBranch === "BASE_BRANCH" ? "cursor-default" : "cursor-pointer"}
          >
            <Badge variant="green">
              <Icon icon="mdi:layers-triple" className="mr-1" />
              {proposedChangesDetails.destination_branch?.value ?? "Base Branch"}
            </Badge>
          </label>
        </div>

        <div className="flex items-center gap-2">
          <Checkbox
            id={"diff"}
            disabled={isPending || !isAuthenticated}
            checked={selectedBranch === "DIFF_BRANCH"}
            onChange={() => handleAccept("DIFF_BRANCH")}
          />
          <label
            htmlFor={"diff"}
            className={selectedBranch === "DIFF_BRANCH" ? "cursor-default" : "cursor-pointer"}
          >
            <Badge variant="blue">
              <Icon icon="mdi:layers-triple" className="mr-1" />
              {proposedChangesDetails.source_branch?.value ?? "Diff Branch"}
            </Badge>
          </label>
        </div>
      </div>
    </div>
  );
};
