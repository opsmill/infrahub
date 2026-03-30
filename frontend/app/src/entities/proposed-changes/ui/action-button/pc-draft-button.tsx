import { Icon } from "@iconify-icon/react";
import { useAtomValue } from "jotai";
import { toast } from "react-toastify";

import { queryClient } from "@/shared/api/rest/client";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { Button } from "@/shared/components/ui/button";
import { Tooltip } from "@/shared/components/ui/tooltip";
import { PROPOSED_CHANGES_OBJECT } from "@/shared/config/constants";

import { useUpdateObjectMutation } from "@/entities/nodes/object/domain/update-object.mutation";
import { proposedChangedState } from "@/entities/proposed-changes/stores/proposedChanges.atom";
import { usePcActionsContext } from "@/entities/proposed-changes/ui/pc-actions-permissions-context";

import type { ProposedChangeActionButtonProps } from "./types";

export const DraftButton = ({ setOpen }: ProposedChangeActionButtonProps) => {
  const { setDraft, unsetDraft } = usePcActionsContext();

  const proposedChangesDetails = useAtomValue(proposedChangedState);

  const isDraft = !!proposedChangesDetails.is_draft.value;

  const { mutate, isPending } = useUpdateObjectMutation({
    onSuccess: async () => {
      queryClient.invalidateQueries({
        predicate: (query) => query.queryKey.includes(proposedChangesDetails.id),
      });
      toast(
        <Alert
          type={ALERT_TYPES.SUCCESS}
          message={isDraft ? "Proposed change opened!" : "Proposed change moved to draft!"}
        />
      );
    },
    onError: () => {
      toast(
        <Alert
          type={ALERT_TYPES.ERROR}
          message={
            isDraft
              ? "An error occurred while removing draft status"
              : "An error occurred while moving to draft"
          }
        />
      );
    },
  });

  const handleAction = (event: React.MouseEvent<HTMLButtonElement>) => {
    event.stopPropagation();

    mutate({
      data: {
        id: proposedChangesDetails.id,
        is_draft: {
          value: !isDraft,
        },
      },
      objectKind: PROPOSED_CHANGES_OBJECT,
    });
  };

  const tooltipContent = isDraft
    ? unsetDraft.unavailability_reason
    : setDraft.unavailability_reason;
  const tooltipEnabled = isDraft ? !unsetDraft.available : !setDraft.available;

  return (
    <>
      <Tooltip content={tooltipContent} enabled={tooltipEnabled} className="whitespace-pre">
        <Button
          className="flex h-full grow flex-wrap gap-2 rounded-r-none border-r-white"
          onClick={handleAction}
          variant={"outline"}
          isLoading={isPending}
          disabled={tooltipEnabled || isPending}
        >
          {isDraft ? "Open" : "Move to draft"}
        </Button>
      </Tooltip>

      <Button
        className="h-full rounded-l-none border-l-0"
        variant={"outline"}
        size={"sm"}
        onClick={() => {
          setOpen(true);
        }}
        disabled={isPending}
        data-testid="proposed-change-action-button-select"
        aria-label="More actions"
        type="button"
      >
        <Icon icon="mdi:unfold-more-horizontal" />
      </Button>
    </>
  );
};
