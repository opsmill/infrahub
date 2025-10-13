import { Icon } from "@iconify-icon/react";
import { useAtomValue } from "jotai/index";
import { toast } from "react-toastify";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import { queryClient } from "@/shared/api/rest/client";
import { Checkbox } from "@/shared/components/inputs/checkbox";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { Badge } from "@/shared/components/ui/badge";
import { Spinner } from "@/shared/components/ui/spinner";

import { useAuth } from "@/entities/authentication/ui/useAuth";
import { useResolveConflictMutation } from "@/entities/diff/domain/resolve-conflict.mutation";
import { proposedChangedState } from "@/entities/proposed-changes/stores/proposedChanges.atom";

export const Conflict = ({ conflict }: any) => {
  const proposedChangesDetails = useAtomValue(proposedChangedState);
  const { mutate, isPending } = useResolveConflictMutation();

  const { isAuthenticated } = useAuth();

  const handleAccept = async (conflictValue: string) => {
    const newValue = conflictValue === conflict.selected_branch ? null : conflictValue;

    mutate(
      {
        id: conflict.uuid,
        selection: newValue,
      },
      {
        onSuccess: async () => {
          await queryClient.invalidateQueries({ queryKey: ["diff-tree"] });
          await graphqlClient.refetchQueries({
            include: ["TASK_DETAILS_CHECK"],
          });

          const message = newValue
            ? "Conflict marked as resolved"
            : "Conflict marked as not resolved";

          toast(<Alert type={ALERT_TYPES.SUCCESS} message={message} />);
        },
        onError: () => {
          toast(
            <Alert
              type={ALERT_TYPES.ERROR}
              message={
                newValue
                  ? "An error occurred while resolving the conflict"
                  : "An error occurred while marking the conflict as not resolved"
              }
            />
          );
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
            disabled={isPending || !isAuthenticated}
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
