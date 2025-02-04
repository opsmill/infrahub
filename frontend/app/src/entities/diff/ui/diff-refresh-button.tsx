import { useUpdateDiffMutation } from "@/entities/diff/domain/update-diff.mutation";
import { Button } from "@/shared/components/buttons/button-primitive";
import { classNames } from "@/shared/utils/common";
import { Icon } from "@iconify-icon/react";

export function DiffRefreshButton({ branchName }: { branchName: string }) {
  const updateDiffMutation = useUpdateDiffMutation();

  return (
    <Button variant="primary-outline" onClick={() => updateDiffMutation.mutate(branchName)}>
      <Icon
        icon="mdi:reload"
        className={classNames("mr-1", updateDiffMutation.isPending && "animate-spin")}
      />
      {updateDiffMutation.isPending ? "Refreshing..." : "Refresh"}
    </Button>
  );
}
