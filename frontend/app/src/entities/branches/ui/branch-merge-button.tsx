import { useQuery } from "@apollo/client";
import { Icon } from "@iconify-icon/react";
import { useAtomValue } from "jotai";
import { toast } from "react-toastify";

import { TASK_OBJECT } from "@/config/constants";

import type { Branch } from "@/shared/api/graphql/generated/graphql";
import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import { Button } from "@/shared/components/buttons/button-primitive";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { datetimeAtom } from "@/shared/stores/time.atom";

import { useAuth } from "@/entities/authentication/ui/useAuth";
import { BRANCH_MERGE } from "@/entities/branches/api/mergeBranch";
import { BRANCH_MERGE_WORKFLOW, TASK_ONGOING_STATES } from "@/entities/tasks/constants";

import { GET_BRANCH_ACTION_STATE } from "../api/getBranchActionState";

type BranchMergeButtonProps = {
  branch: Branch;
};

export const BranchMergeButton = ({ branch }: BranchMergeButtonProps) => {
  const { isAuthenticated } = useAuth();
  const date = useAtomValue(datetimeAtom);

  const { loading, data } = useQuery(GET_BRANCH_ACTION_STATE, {
    variables: {
      branch: branch.name,
      workflow: [BRANCH_MERGE_WORKFLOW],
      state: TASK_ONGOING_STATES,
    },
    pollInterval: 5000,
  });

  const taskData = data?.[TASK_OBJECT];

  const handleSubmit = async () => {
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

      toast(<Alert type={ALERT_TYPES.SUCCESS} message={"Branch merge requested!"} />, {
        toastId: "alert-success",
      });
    } catch (error) {
      console.error(error);
      toast(
        <Alert type={ALERT_TYPES.ERROR} message={"An error occurred while merging the branch"} />
      );
    }
  };

  return (
    <Button
      disabled={!isAuthenticated || loading || branch.is_default || taskData?.count > 0}
      onClick={handleSubmit}
      variant={"active"}
      className="flex items-center gap-2"
    >
      Merge
      <Icon icon={"mdi:check"} />
    </Button>
  );
};
