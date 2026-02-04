import { toast } from "react-toastify";

import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { Button, type ButtonProps } from "@/shared/components/ui/button";

import { useRebaseBranch } from "@/entities/branches/domain/rebase-branch";
import { useUpdateDiffMutation } from "@/entities/diff/domain/update-diff.mutation";

export interface DiffRebaseButtonProps extends ButtonProps {
  branchName: string;
}

export function DiffRebaseButton({ branchName, ...props }: DiffRebaseButtonProps) {
  const updateDiffMutation = useUpdateDiffMutation();
  const rebaseBranchMutation = useRebaseBranch();

  const handleRebase = async () => {
    try {
      await rebaseBranchMutation.mutateAsync({ branchName });
      toast(<Alert type={ALERT_TYPES.SUCCESS} message="Branch rebased!" />);
      await updateDiffMutation.mutateAsync(branchName);
    } catch (error: unknown) {
      if (error instanceof Error) {
        toast(<Alert type={ALERT_TYPES.ERROR} message={error.message} />);
      }
    }
  };

  return (
    <Button
      size="sm"
      variant="primary-outline"
      onClick={handleRebase}
      isLoading={rebaseBranchMutation.isPending}
      disabled={rebaseBranchMutation.isPending}
      {...props}
    >
      Rebase
    </Button>
  );
}
