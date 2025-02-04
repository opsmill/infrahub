import { useUpdateDiffMutation } from "@/entities/diff/domain/update-diff.mutation";
import { Button, ButtonProps } from "@/shared/components/buttons/button-primitive";
import { classNames } from "@/shared/utils/common";
import { Icon } from "@iconify-icon/react";

export interface DiffRefreshButtonProps extends Omit<ButtonProps, "onClick"> {
  branchName: string;
}

export function DiffRefreshButton({ branchName, ...props }: DiffRefreshButtonProps) {
  const updateDiffMutation = useUpdateDiffMutation();

  return (
    <Button
      variant="primary-outline"
      onClick={() => updateDiffMutation.mutate(branchName)}
      {...props}
    >
      <Icon
        icon="mdi:reload"
        className={classNames("mr-1", updateDiffMutation.isPending && "animate-spin")}
      />
      {updateDiffMutation.isPending ? "Refreshing diff..." : "Refresh diff"}
    </Button>
  );
}
