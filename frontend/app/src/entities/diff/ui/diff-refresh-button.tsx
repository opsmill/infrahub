import { Icon } from "@iconify-icon/react";
import { Button, type ButtonProps } from "@infrahub/ui";
import { useMutationState } from "@tanstack/react-query";
import { toast } from "react-toastify";

import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { classNames } from "@/shared/utils/common";

import { updateDiffMutationKeys } from "@/entities/diff/ui/queries/diff.query-keys";
import { useUpdateDiffMutation } from "@/entities/diff/ui/queries/update-diff.mutation";

export interface DiffRefreshButtonProps extends Omit<ButtonProps, "onPress"> {
  branchName: string;
}

export function DiffRefreshButton({ branchName, ...props }: DiffRefreshButtonProps) {
  const updateDiffMutation = useUpdateDiffMutation();
  const allUpdatingDiffs = useMutationState({
    filters: { status: "pending", mutationKey: updateDiffMutationKeys.all },
    select: (mutation) => mutation.state.variables,
  });

  const isLoading = allUpdatingDiffs.includes(branchName);

  const handleRefreshDiff = async () => {
    updateDiffMutation.mutate(branchName, {
      // tree + summary invalidation lives in useUpdateDiffMutation itself.
      onSuccess: () => {
        toast(<Alert type={ALERT_TYPES.SUCCESS} message="Diff updated!" />);
      },
      onError: (error) => {
        toast(<Alert type={ALERT_TYPES.ERROR} message={error.message} />);
      },
    });
  };

  return (
    <Button variant="primary-outline" onPress={handleRefreshDiff} {...props}>
      <Icon icon="mdi:reload" className={classNames(isLoading && "animate-spin")} />
      {isLoading ? "Refreshing diff..." : "Refresh diff"}
    </Button>
  );
}
