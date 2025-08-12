import { PROPOSED_CHANGES_OBJECT } from "@/config/constants";
import { useUpdateObjectMutation } from "@/entities/nodes/object/domain/update-object.mutation";
import { proposedChangedState } from "@/entities/proposed-changes/stores/proposedChanges.atom";
import { usePcActionsContext } from "@/entities/proposed-changes/ui/pc-actions-permissions-context";
import { queryClient } from "@/shared/api/rest/client";
import { Button } from "@/shared/components/buttons/button-primitive";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { Tooltip } from "@/shared/components/ui/tooltip";
import { Icon } from "@iconify-icon/react";
import { useAtomValue } from "jotai";
import { toast } from "react-toastify";
import { ProposedChangeActionButtonProps } from "./types";

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
          className="grow flex flex-wrap gap-2 h-full rounded-r-none border-r-white"
          onClick={handleAction}
          variant={"primary"}
          isLoading={isPending}
          disabled={tooltipEnabled || isPending}
        >
          {isDraft ? "Open" : "Move to draft"}
        </Button>
      </Tooltip>

      <Button
        className="h-full rounded-l-none border-l-0"
        variant={"primary"}
        size={"sm"}
        onClick={() => {
          setOpen(true);
        }}
        disabled={isPending}
        data-testid="proposed-change-action-button-select"
      >
        <Icon icon="mdi:unfold-more-horizontal" />
      </Button>
    </>
  );
};
