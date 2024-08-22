import { Button, ButtonProps } from "@/components/buttons/button-primitive";
import React, { useState } from "react";
import { useAuth } from "@/hooks/useAuth";
import { DIFF_UPDATE } from "@/graphql/mutations/proposed-changes/diff/diff-update";
import { useMutation } from "@/hooks/useQuery";
import { toast } from "react-toastify";
import { Alert, ALERT_TYPES } from "@/components/ui/alert";
import graphqlClient from "@/graphql/graphqlClientApollo";
import { DateDisplay } from "@/components/display/date-display";

interface PcDiffUpdateButtonProps extends ButtonProps {
  sourceBranch: string;
  time?: string;
  hideText?: boolean;
}

export const PcDiffUpdateButton = ({ sourceBranch, time, ...props }: PcDiffUpdateButtonProps) => {
  const auth = useAuth();
  const [isLoadingUpdate, setIsLoadingUpdate] = useState(false);

  const [scheduleDiffTreeUpdate] = useMutation(DIFF_UPDATE, {
    variables: { branchName: sourceBranch, wait: true },
  });

  const handleSubmit = async () => {
    setIsLoadingUpdate(true);
    await scheduleDiffTreeUpdate();
    setIsLoadingUpdate(false);
    await graphqlClient.refetchQueries({ include: ["GET_PROPOSED_CHANGES_DIFF_TREE"] });
    toast(<Alert type={ALERT_TYPES.SUCCESS} message="Diff updated!" />);
  };

  return (
    <div className="flex items-center">
      {!!time && (
        <div className="flex items-center text-xs mr-2">
          <span className="mr-1">Updated</span>
          <DateDisplay date={time} />
        </div>
      )}

      <Button
        variant="outline"
        onClick={handleSubmit}
        isLoading={isLoadingUpdate}
        disabled={!auth?.permissions?.write || isLoadingUpdate}
        {...props}>
        {isLoadingUpdate ? "Updating diff..." : "Update diff"}
      </Button>
    </div>
  );
};
