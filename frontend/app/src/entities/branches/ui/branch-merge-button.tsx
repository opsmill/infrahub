import { useQuery } from "@apollo/client";
import { Icon } from "@iconify-icon/react";
import { useAtomValue } from "jotai";
import { useState } from "react";
import { toast } from "react-toastify";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import { Button } from "@/shared/components/aria/button";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { TASK_OBJECT } from "@/shared/config/constants";
import { datetimeAtom } from "@/shared/stores/time.atom";

import { useAuth } from "@/entities/authentication/ui/useAuth";
import { GET_BRANCH_ACTION_STATE } from "@/entities/branches/api/getBranchActionState";
import { BRANCH_MERGE } from "@/entities/branches/api/mergeBranch";
import { BRANCH_STATUS } from "@/entities/branches/constants";
import type { BranchDetail } from "@/entities/branches/domain/branch.mappers";
import { useNavigateAfterBranchRemoval } from "@/entities/branches/ui/hooks/use-navigate-after-branch-removal";
import { useConfig } from "@/entities/config/ui/config-provider";
import { BRANCH_MERGE_WORKFLOW, TASK_ONGOING_STATES } from "@/entities/tasks/constants";

type BranchMergeButtonProps = {
  branch: BranchDetail;
};

export const BranchMergeButton = ({ branch }: BranchMergeButtonProps) => {
  const { isAuthenticated } = useAuth();
  const date = useAtomValue(datetimeAtom);
  const config = useConfig();
  const { navigateToPage } = useNavigateAfterBranchRemoval();
  const [isMergeRequested, setIsMergeRequested] = useState(false);

  const { loading, data, refetch } = useQuery(GET_BRANCH_ACTION_STATE, {
    variables: {
      branch: branch.name,
      workflow: [BRANCH_MERGE_WORKFLOW],
      state: TASK_ONGOING_STATES,
    },
    pollInterval: 5000,
  });

  const taskData = data?.[TASK_OBJECT];
  const hasOngoingTask = !!taskData?.count && taskData.count > 0;

  const isDisabled =
    !isAuthenticated ||
    loading ||
    !!branch.is_default ||
    branch.status === BRANCH_STATUS.MERGED ||
    isMergeRequested ||
    hasOngoingTask;

  const handleSubmit = async () => {
    setIsMergeRequested(true);

    try {
      await graphqlClient.mutate({
        mutation: BRANCH_MERGE,
        variables: { name: branch.name },
        context: { branch: branch.name, date },
      });

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
