import { Button, ButtonProps } from "@/components/buttons/button-primitive";
import React, { useState } from "react";
import { useAuth } from "@/hooks/useAuth";
import { DIFF_UPDATE } from "@/graphql/mutations/proposed-changes/diff/diff-update";
import { useMutation } from "@/hooks/useQuery";
import { toast } from "react-toastify";
import { Alert, ALERT_TYPES } from "@/components/ui/alert";

interface PcDiffUpdateButtonProps extends ButtonProps {
  sourceBranch: String;
}

export const PcDiffUpdateButton = ({ sourceBranch, ...props }: PcDiffUpdateButtonProps) => {
  const auth = useAuth();
  const [isLoadingUpdate, setIsLoadingUpdate] = useState(false);

  const [scheduleDiffTreeUpdate] = useMutation(DIFF_UPDATE, {
    variables: { branchName: sourceBranch, wait: true },
  });

  const handleSubmit = async () => {
    setIsLoadingUpdate(true);
    await scheduleDiffTreeUpdate();
    setIsLoadingUpdate(false);
    toast(<Alert type={ALERT_TYPES.SUCCESS} message="Diff updated!" />);
  };

  return (
    <div className="flex items-center">
      {/* <span className=" text-xs mr-1">last diff update</span> */}

      <Button
        variant="primary"
        onClick={handleSubmit}
        isLoading={isLoadingUpdate}
        disabled={!auth?.permissions?.write || isLoadingUpdate}
        {...props}>
        {isLoadingUpdate ? "Updating diff..." : "Update diff"}
      </Button>
    </div>
  );
};
