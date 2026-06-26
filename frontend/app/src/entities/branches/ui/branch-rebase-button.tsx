import { Icon } from "@iconify-icon/react";
import { Button } from "@infrahub/ui";
import { toast } from "react-toastify";

import { BranchStatus } from "@/shared/api/graphql/generated/types";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";

import { useAuth } from "@/entities/authentication/ui/useAuth";
import type { BranchDetail } from "@/entities/branches/domain/branch.mappers";
import { useGetBranchActionState } from "@/entities/branches/ui/queries/get-branch-action-state.query";
import { useRebaseBranch } from "@/entities/branches/ui/queries/rebase-branch.mutation";
import { BRANCH_REBASE_WORKFLOW, TASK_ONGOING_STATES } from "@/entities/tasks/constants";

type BranchRebaseButtonProps = {
  branch: BranchDetail;
};

export const BranchRebaseButton = ({ branch }: BranchRebaseButtonProps) => {
  const { isAuthenticated } = useAuth();
  const rebaseBranchMutation = useRebaseBranch();

  const { isPending, data, refetch } = useGetBranchActionState({
    branchName: branch.name,
    workflow: [BRANCH_REBASE_WORKFLOW],
    state: TASK_ONGOING_STATES,
  });

  const hasOngoingTask = (data?.ongoingTaskCount ?? 0) > 0;
  const isDisabled =
    !isAuthenticated ||
    isPending ||
    !!branch.is_default ||
    branch.status === BranchStatus.MERGED ||
    hasOngoingTask;

  const handleRebase = () => {
    rebaseBranchMutation.mutate(
      {
        branchName: branch.name,
        waitUntilCompletion: false,
      },
      {
        onSuccess: async () => {
          toast(<Alert type={ALERT_TYPES.SUCCESS} message="Branch rebase requested!" />, {
            toastId: "alert-success",
          });
          await refetch();
        },
        onError: (error) => {
          console.error("Error while rebasing branch: ", error);
          toast(
            <Alert type={ALERT_TYPES.ERROR} message="An error occurred while rebasing the branch" />
          );
        },
      }
    );
  };

  return (
    <Button
      isDisabled={isDisabled}
      onPress={handleRebase}
      variant="outline"
      className="flex items-center gap-2"
    >
      Rebase
      <Icon icon="mdi:counterclockwise-arrows" />
    </Button>
  );
};
