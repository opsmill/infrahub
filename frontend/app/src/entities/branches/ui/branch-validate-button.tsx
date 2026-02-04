import { useQuery } from "@apollo/client";
import { Icon } from "@iconify-icon/react";
import { useAtomValue } from "jotai";
import { toast } from "react-toastify";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { Button } from "@/shared/components/ui/button";
import { TASK_OBJECT } from "@/shared/config/constants";
import { datetimeAtom } from "@/shared/stores/time.atom";

import { useAuth } from "@/entities/authentication/ui/useAuth";
import { BRANCH_VALIDATE } from "@/entities/branches/api/validateBranch";
import type { BranchDetail } from "@/entities/branches/domain/branch.mappers";
import { BRANCH_VALIDATE_WORKFLOW, TASK_ONGOING_STATES } from "@/entities/tasks/constants";

import { GET_BRANCH_ACTION_STATE } from "../api/getBranchActionState";

type BranchValidateButtonProps = {
  branch: BranchDetail;
};

export const BranchValidateButton = ({ branch }: BranchValidateButtonProps) => {
  const { isAuthenticated } = useAuth();
  const date = useAtomValue(datetimeAtom);

  const { loading, data } = useQuery(GET_BRANCH_ACTION_STATE, {
    variables: {
      branch: branch.name,
      workflow: [BRANCH_VALIDATE_WORKFLOW],
      state: TASK_ONGOING_STATES,
    },
    pollInterval: 5000,
  });

  const taskData = data?.[TASK_OBJECT];

  const handleSubmit = async () => {
    try {
      await graphqlClient.mutate({
        mutation: BRANCH_VALIDATE,
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
      disabled={
        !isAuthenticated ||
        loading ||
        branch.is_default ||
        (!!taskData?.count && taskData.count > 0)
      }
      onClick={handleSubmit}
      variant={"warning"}
      className="flex items-center gap-2"
    >
      Validate
      <Icon icon={"mdi:shield-check-outline"} />
    </Button>
  );
};
