import {
  UPDATE_DIFF_KEY,
  useUpdateDiffMutation,
} from "@/entities/diff/domain/update-diff.mutation";
import { Button, ButtonProps } from "@/shared/components/buttons/button-primitive";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { classNames } from "@/shared/utils/common";
import { Icon } from "@iconify-icon/react";
import { useMutationState } from "@tanstack/react-query";
import { toast } from "react-toastify";

export interface DiffRefreshButtonProps extends Omit<ButtonProps, "onClick"> {
  branchName: string;
}

export function DiffRefreshButton({ branchName, ...props }: DiffRefreshButtonProps) {
  const updateDiffMutation = useUpdateDiffMutation();
  const allUpdatingDiffs = useMutationState({
    filters: { status: "pending", mutationKey: [UPDATE_DIFF_KEY] },
    select: (mutation) => mutation.state.variables,
  });

  const isLoading = allUpdatingDiffs.includes(branchName);

  const handleRefreshDiff = async () => {
    try {
      await updateDiffMutation.mutateAsync(branchName);
      toast(<Alert type={ALERT_TYPES.SUCCESS} message="Diff updated!" />);
    } catch (error: unknown) {
      if (error instanceof Error) {
        toast(<Alert type={ALERT_TYPES.ERROR} message={error.message} />);
      }
    }
  };

  return (
    <Button variant="primary-outline" onClick={handleRefreshDiff} {...props}>
      <Icon icon="mdi:reload" className={classNames("mr-1", isLoading && "animate-spin")} />
      {isLoading ? "Refreshing diff..." : "Refresh diff"}
    </Button>
  );
}
