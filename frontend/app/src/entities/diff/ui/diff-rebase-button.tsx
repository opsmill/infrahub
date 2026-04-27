import { toast } from "react-toastify";

import { Button, type ButtonProps } from "@/shared/components/aria/button";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";

import { useRebaseBranch } from "@/entities/branches/ui/queries/rebase-branch.mutation";
import { useUpdateDiffMutation } from "@/entities/diff/ui/queries/update-diff.mutation";

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
      onPress={handleRebase}
      isPending={rebaseBranchMutation.isPending}
      isDisabled={rebaseBranchMutation.isPending}
      {...props}
    >
      Rebase
    </Button>
  );
}
