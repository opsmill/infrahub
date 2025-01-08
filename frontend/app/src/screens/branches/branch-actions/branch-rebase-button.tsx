import { Button } from "@/components/buttons/button-primitive";
import { ALERT_TYPES, Alert } from "@/components/ui/alert";
import { TASK_OBJECT } from "@/config/constants";
import { Branch } from "@/generated/graphql";
import graphqlClient from "@/graphql/graphqlClientApollo";
import { BRANCH_REBASE } from "@/graphql/mutations/branches/rebaseBranch";
import { useAuth } from "@/hooks/useAuth";
import { BRANCH_REBASE_WORKFLOW, TASK_ONGOING_STATES } from "@/screens/tasks/constants";
import { datetimeAtom } from "@/state/atoms/time.atom";
import { useQuery } from "@apollo/client";
import { Icon } from "@iconify-icon/react";
import { useAtomValue } from "jotai";
import { toast } from "react-toastify";
import { GET_BRANCH_ACTION_STATE } from "./graphql/getBranchActionState";

type BranchRebaseButtonProps = {
  branch: Branch;
};

export const BranchRebaseButton = ({ branch }: BranchRebaseButtonProps) => {
  const { isAuthenticated } = useAuth();
  const date = useAtomValue(datetimeAtom);

  const { loading, data } = useQuery(GET_BRANCH_ACTION_STATE, {
    variables: {
      branch: branch.name,
      workflow: [BRANCH_REBASE_WORKFLOW],
      state: TASK_ONGOING_STATES,
    },
    pollInterval: 5_000,
  });

  const taskData = data?.[TASK_OBJECT];

  const handleSubmit = async () => {
    try {
      await graphqlClient.mutate({
        mutation: BRANCH_REBASE,
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
      variant={"outline"}
      className="flex items-center gap-2"
    >
      Rebase
      <Icon icon={"mdi:counterclockwise-arrows"} />
    </Button>
  );
};
