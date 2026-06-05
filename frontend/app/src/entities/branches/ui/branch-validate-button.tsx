import { Icon } from "@iconify-icon/react";
import { Button } from "@infrahub/ui";
import { toast } from "react-toastify";

import { BranchStatus } from "@/shared/api/graphql/generated/types";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";

import { useAuth } from "@/entities/authentication/ui/useAuth";
import type { BranchDetail } from "@/entities/branches/domain/branch.mappers";
import { useGetBranchActionState } from "@/entities/branches/ui/queries/get-branch-action-state.query";
import { useValidateBranch } from "@/entities/branches/ui/queries/validate-branch.mutation";
import { BRANCH_VALIDATE_WORKFLOW, TASK_ONGOING_STATES } from "@/entities/tasks/constants";

type BranchValidateButtonProps = {
  branch: BranchDetail;
};

export const BranchValidateButton = ({ branch }: BranchValidateButtonProps) => {
  const { isAuthenticated } = useAuth();

  const { isPending, data } = useGetBranchActionState({
    branchName: branch.name,
    workflow: [BRANCH_VALIDATE_WORKFLOW],
    state: TASK_ONGOING_STATES,
  });

  const validateMutation = useValidateBranch();

  const hasOngoingTask = (data?.ongoingTaskCount ?? 0) > 0;
  const isDisabled =
    !isAuthenticated ||
    isPending ||
    !!branch.is_default ||
    branch.status === BranchStatus.MERGED ||
    hasOngoingTask;

  const handleSubmit = async () => {
    try {
      await validateMutation.mutateAsync({ branchName: branch.name });
      toast(<Alert type={ALERT_TYPES.SUCCESS} message="Branch validation requested!" />, {
        toastId: "alert-success",
      });
    } catch (error) {
      console.error(error);
      toast(
        <Alert type={ALERT_TYPES.ERROR} message="An error occurred while validating the branch" />
      );
    }
  };

  return (
    <Button
      isDisabled={isDisabled}
      onPress={handleSubmit}
      variant="warning"
      className="flex items-center gap-2"
    >
      Validate
      <Icon icon="mdi:shield-check-outline" />
    </Button>
  );
};
