import { Icon } from "@iconify-icon/react";
import { Button } from "@infrahub/ui";
import { toast } from "react-toastify";

import { queryClient } from "@/shared/api/rest/client";
import { Tooltip } from "@/shared/components/aria/tooltip";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { PROPOSED_CHANGES_OBJECT } from "@/shared/config/constants";

import { useUpdateObjectMutation } from "@/entities/nodes/object/ui/queries/update-object.mutation";
import { CLOSE_STATE } from "@/entities/proposed-changes/constants";
import { useProposedChange } from "@/entities/proposed-changes/ui/hooks/use-proposed-change";
import { usePcActionsContext } from "@/entities/proposed-changes/ui/pc-actions-permissions-context";

import type { ProposedChangeActionButtonProps } from "./types";

export const CloseButton = ({ setOpen }: ProposedChangeActionButtonProps) => {
  const { close } = usePcActionsContext();

  const proposedChangesDetails = useProposedChange();

  const { mutate, isPending } = useUpdateObjectMutation({
    onSuccess: async () => {
      queryClient.invalidateQueries({
        predicate: (query) => query.queryKey.includes(proposedChangesDetails.id),
      });
      toast(<Alert type={ALERT_TYPES.SUCCESS} message={"Proposed change closed!"} />);
    },
    onError: (error) => {
      toast(<Alert type={ALERT_TYPES.ERROR} message={error.message} />);
    },
  });

  const handleAction = () => {
    mutate({
      data: {
        id: proposedChangesDetails.id,
        state: {
          value: CLOSE_STATE,
        },
      },
      objectKind: PROPOSED_CHANGES_OBJECT,
    });
  };

  const tooltipMessage = close.unavailability_reason;
  const isUnavailable = !close.available;

  return (
    <>
      <Tooltip message={isUnavailable ? tooltipMessage : undefined} className="whitespace-pre">
        <Button
          className="flex h-full grow flex-wrap gap-2 rounded-r-none border-r-white"
          onPress={handleAction}
          variant={"danger"}
          isPending={isPending}
          isDisabled={isUnavailable || isPending}
          isDisabledAndFocusable={isUnavailable && !isPending}
        >
          Close
        </Button>
      </Tooltip>

      <Button
        className="h-full rounded-l-none border-l-0"
        variant={"danger"}
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
