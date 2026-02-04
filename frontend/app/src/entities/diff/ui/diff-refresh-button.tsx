import { Icon } from "@iconify-icon/react";
import { useMutationState } from "@tanstack/react-query";
import { toast } from "react-toastify";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import { queryClient } from "@/shared/api/rest/client";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { Button, type ButtonProps } from "@/shared/components/ui/button";
import { classNames } from "@/shared/utils/common";

import { treeQueryKeys, updateDiffMutationKeys } from "@/entities/diff/domain/diff.query-keys";
import { useUpdateDiffMutation } from "@/entities/diff/domain/update-diff.mutation";

export interface DiffRefreshButtonProps extends Omit<ButtonProps, "onClick"> {
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
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: treeQueryKeys.all });
        graphqlClient.refetchQueries({
          include: ["GET_PROPOSED_CHANGES_DIFF_SUMMARY"],
        });
        toast(<Alert type={ALERT_TYPES.SUCCESS} message="Diff updated!" />);
      },
      onError: (error) => {
        toast(<Alert type={ALERT_TYPES.ERROR} message={error.message} />);
      },
    });
  };

  return (
    <Button variant="primary-outline" onClick={handleRefreshDiff} {...props}>
      <Icon icon="mdi:reload" className={classNames("mr-1", isLoading && "animate-spin")} />
      {isLoading ? "Refreshing diff..." : "Refresh diff"}
    </Button>
  );
}
