import { useQuery } from "@apollo/client";
import { Icon } from "@iconify-icon/react";
import { toast } from "react-toastify";

import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { Button } from "@/shared/components/ui/button";
import { TASK_OBJECT } from "@/shared/config/constants";

import { useAuth } from "@/entities/authentication/ui/useAuth";
import { BRANCH_STATUS } from "@/entities/branches/constants";
import type { BranchDetail } from "@/entities/branches/domain/branch.mappers";
import { useRebaseBranch } from "@/entities/branches/domain/rebase-branch";
import { BRANCH_REBASE_WORKFLOW, TASK_ONGOING_STATES } from "@/entities/tasks/constants";

import { GET_BRANCH_ACTION_STATE } from "../api/getBranchActionState";

type BranchRebaseButtonProps = {
  branch: BranchDetail;
};

export const BranchRebaseButton = ({ branch }: BranchRebaseButtonProps) => {
  const { isAuthenticated } = useAuth();
  const rebaseBranchMutation = useRebaseBranch();

  const { loading, data, refetch } = useQuery(GET_BRANCH_ACTION_STATE, {
    variables: {
      branch: branch.name,
      workflow: [BRANCH_REBASE_WORKFLOW],
      state: TASK_ONGOING_STATES,
    },
    pollInterval: 5000,
  });

  const taskData = data?.[TASK_OBJECT];
  const isMerged = branch.status === BRANCH_STATUS.MERGED;
  const isDisabled =
    !isAuthenticated ||
    loading ||
    !!branch.is_default ||
    isMerged ||
    !!(taskData?.count && taskData.count > 0);

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
            <Alert
              type={ALERT_TYPES.ERROR}
              message={"An error occurred while merging the branch"}
            />
          );
        },
      }
    );
  };

  return (
    <Button
      disabled={isDisabled}
      onClick={handleRebase}
      variant={"outline"}
      className="flex items-center gap-2"
    >
      Rebase
      <Icon icon={"mdi:counterclockwise-arrows"} />
    </Button>
  );
};
