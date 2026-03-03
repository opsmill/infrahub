import { useQuery } from "@apollo/client";
import { Icon } from "@iconify-icon/react";
import { useAtomValue } from "jotai";
import { useEffect, useState } from "react";
import { toast } from "react-toastify";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { Button } from "@/shared/components/ui/button";
import { TASK_OBJECT } from "@/shared/config/constants";
import { datetimeAtom } from "@/shared/stores/time.atom";

import { useAuth } from "@/entities/authentication/ui/useAuth";
import { GET_BRANCH_ACTION_STATE } from "@/entities/branches/api/getBranchActionState";
import { BRANCH_MERGE } from "@/entities/branches/api/mergeBranch";
import { BRANCH_STATUS } from "@/entities/branches/constants";
import type { BranchDetail } from "@/entities/branches/domain/branch.mappers";
import { BRANCH_MERGE_WORKFLOW, TASK_ONGOING_STATES } from "@/entities/tasks/constants";

type BranchMergeButtonProps = {
  branch: BranchDetail;
};

export const BranchMergeButton = ({ branch }: BranchMergeButtonProps) => {
  const { isAuthenticated } = useAuth();
  const date = useAtomValue(datetimeAtom);
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

  // Reset local state when server confirms no ongoing merge task
  useEffect(() => {
    if (!loading && !hasOngoingTask) {
      setIsMergeRequested(false);
    }
  }, [loading, hasOngoingTask]);

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
        variables: {
          name: branch.name,
        },
        context: {
          branch: branch.name,
          date,
        },
      });

      toast(<Alert type={ALERT_TYPES.SUCCESS} message="Branch merge requested!" />, {
        toastId: "alert-success",
      });

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
      disabled={isDisabled}
      onClick={handleSubmit}
      variant="active"
      className="flex items-center gap-2"
    >
      Merge
      <Icon icon="mdi:check" />
    </Button>
  );
};
