import { Icon } from "@iconify-icon/react";
import { Button } from "@infrahub/ui";
import { toast } from "react-toastify";

import { queryClient } from "@/shared/api/rest/client";
import { Tooltip } from "@/shared/components/aria/tooltip";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { PROPOSED_CHANGES_OBJECT } from "@/shared/config/constants";

import { useNavigateAfterBranchRemoval } from "@/entities/branches/ui/hooks/use-navigate-after-branch-removal";
import { useConfig } from "@/entities/config/ui/config-provider";
import { useUpdateObjectMutation } from "@/entities/nodes/object/ui/queries/update-object.mutation";
import { MERGE_STATE } from "@/entities/proposed-changes/constants";
import { useProposedChange } from "@/entities/proposed-changes/stores/proposedChanges.atom";
import { usePcActionsContext } from "@/entities/proposed-changes/ui/pc-actions-permissions-context";

import type { ProposedChangeActionButtonProps } from "./types";

export const MergeButton = ({ setOpen }: ProposedChangeActionButtonProps) => {
  const { merge } = usePcActionsContext();

  const proposedChangesDetails = useProposedChange();
  const config = useConfig();
  const { clearBranchIfCurrent } = useNavigateAfterBranchRemoval();

  const { mutate, isPending } = useUpdateObjectMutation({
    onSuccess: async () => {
      queryClient.invalidateQueries({
        predicate: (query) => query.queryKey.includes(proposedChangesDetails.id),
      });
      const deleteBranchAfterMerge = config.main.delete_branch_after_merge;
      const sourceBranch = proposedChangesDetails.source_branch?.value;

      const message =
        deleteBranchAfterMerge && sourceBranch
          ? `Proposed change merged! Branch '${sourceBranch}' will be automatically deleted.`
          : "Proposed change merged!";

      toast(<Alert type={ALERT_TYPES.SUCCESS} message={message} />);

      if (deleteBranchAfterMerge && sourceBranch) {
        clearBranchIfCurrent(sourceBranch);
      }
    },
    onError: () => {
      toast(
        <Alert
          type={ALERT_TYPES.ERROR}
          message={"An error occurred while merging proposed change"}
        />
      );
    },
  });

  const handleAction = () => {
    mutate({
      data: {
        id: proposedChangesDetails.id,
        state: {
          value: MERGE_STATE,
        },
      },
      objectKind: PROPOSED_CHANGES_OBJECT,
    });
  };

  const tooltipMessage = merge.unavailability_reason;
  const isUnavailable = !merge.available;

  return (
    <>
      <Tooltip message={isUnavailable ? tooltipMessage : undefined} className="whitespace-pre">
        <Button
          className="flex h-full grow flex-wrap gap-2 rounded-r-none border-r-white"
          onPress={handleAction}
          variant={"active"}
          isPending={isPending}
          isDisabled={isUnavailable || isPending}
          isDisabledAndFocusable={isUnavailable && !isPending}
        >
          Merge
        </Button>
      </Tooltip>

      <Button
        className="h-full rounded-l-none border-l-0"
        variant={"active"}
        size={"sm"}
        onPress={() => {
          setOpen(true);
        }}
        isDisabled={isPending}
        data-testid="proposed-change-action-button-select"
        aria-label="More actions"
      >
        <Icon icon="mdi:unfold-more-horizontal" />
      </Button>
    </>
  );
};
