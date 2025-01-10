import { Button } from "@/components/buttons/button-primitive";
import { ALERT_TYPES, Alert } from "@/components/ui/alert";
import { TASK_OBJECT } from "@/config/constants";
import { useAuth } from "@/hooks/useAuth";
import { BRANCH_VALIDATE_WORKFLOW, TASK_ONGOING_STATES } from "@/screens/tasks/constants";
import { Branch } from "@/shared/api/graphql/generated/graphql";
import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import { BRANCH_VALIDATE } from "@/shared/api/graphql/mutations/branches/validateBranch";
import { datetimeAtom } from "@/state/atoms/time.atom";
import { useQuery } from "@apollo/client";
import { Icon } from "@iconify-icon/react";
import { useAtomValue } from "jotai";
import { toast } from "react-toastify";
import { GET_BRANCH_ACTION_STATE } from "./graphql/getBranchActionState";

type BranchValidateButtonProps = {
  branch: Branch;
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
    pollInterval: 5_000,
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
      disabled={!isAuthenticated || loading || branch.is_default || taskData?.count > 0}
      onClick={handleSubmit}
      variant={"warning"}
      className="flex items-center gap-2"
    >
      Validate
      <Icon icon={"mdi:shield-check-outline"} />
    </Button>
  );
};
