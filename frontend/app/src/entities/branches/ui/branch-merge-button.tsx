import { Icon } from "@iconify-icon/react";
import { Button } from "@infrahub/ui";
import { useState } from "react";
import { toast } from "react-toastify";

import { BranchStatus } from "@/shared/api/graphql/generated/types";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";

import { useAuth } from "@/entities/authentication/ui/useAuth";
import type { BranchDetail } from "@/entities/branches/domain/branch.mappers";
import { useNavigateAfterBranchRemoval } from "@/entities/branches/ui/hooks/use-navigate-after-branch-removal";
import { useGetBranchActionState } from "@/entities/branches/ui/queries/get-branch-action-state.query";
import { useMergeBranch } from "@/entities/branches/ui/queries/merge-branch.mutation";
import { useConfig } from "@/entities/config/ui/config-provider";
import { BRANCH_MERGE_WORKFLOW, TASK_ONGOING_STATES } from "@/entities/tasks/constants";

type BranchMergeButtonProps = {
  branch: BranchDetail;
};

export const BranchMergeButton = ({ branch }: BranchMergeButtonProps) => {
  const { isAuthenticated } = useAuth();
  const config = useConfig();
  const { navigateToPage } = useNavigateAfterBranchRemoval();
  const [isMergeRequested, setIsMergeRequested] = useState(false);

  const { isPending, data, refetch } = useGetBranchActionState({
    branchName: branch.name,
    workflow: [BRANCH_MERGE_WORKFLOW],
    state: TASK_ONGOING_STATES,
  });

  const mergeMutation = useMergeBranch();

  const hasOngoingTask = (data?.ongoingTaskCount ?? 0) > 0;
  const isDisabled =
    !isAuthenticated ||
    isPending ||
    !!branch.is_default ||
    branch.status === BranchStatus.MERGED ||
    isMergeRequested ||
    hasOngoingTask;

  const handleSubmit = async () => {
    setIsMergeRequested(true);

    try {
      await mergeMutation.mutateAsync({ branchName: branch.name });

      const deleteBranchAfterMerge = config.main.delete_branch_after_merge;

      const message = deleteBranchAfterMerge
        ? `Branch merge requested! Branch '${branch.name}' will be automatically deleted.`
        : "Branch merge requested!";

      toast(<Alert type={ALERT_TYPES.SUCCESS} message={message} />, {
        toastId: "alert-success",
      });

      if (deleteBranchAfterMerge) {
        navigateToPage("/branches", branch.name);
      }

      await refetch();
    } catch (error) {
      console.error(error);
      setIsMergeRequested(false);
      toast(
        <Alert type={ALERT_TYPES.ERROR} message="An error occurred while merging the branch" />
      );
    }
  };

  return (
    <Button
      isDisabled={isDisabled}
      onPress={handleSubmit}
      variant="active"
      className="flex items-center gap-2"
    >
      Merge
      <Icon icon="mdi:check" />
    </Button>
  );
};
