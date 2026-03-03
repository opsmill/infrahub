import { Icon } from "@iconify-icon/react";
import { useAtomValue } from "jotai";
import { toast } from "react-toastify";

import { queryClient } from "@/shared/api/rest/client";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { Button } from "@/shared/components/ui/button";
import { Tooltip } from "@/shared/components/ui/tooltip";

import { useAuth } from "@/entities/authentication/ui/useAuth";
import { APPROVE_DECISION, CANCEL_APPROVE_DECISION } from "@/entities/proposed-changes/constants";
import { proposedChangedState } from "@/entities/proposed-changes/stores/proposedChanges.atom";
import { usePcActionsContext } from "@/entities/proposed-changes/ui/pc-actions-permissions-context";
import { useUpdateProposedChangeReview } from "@/entities/proposed-changes/ui/queries/update-review.mutation";
import { hasUserApprovedProposedChange } from "@/entities/proposed-changes/utils/has-user-approved-proposed-change";

import type { ProposedChangeActionButtonProps } from "./types";

export const ApproveButton = ({ setOpen }: ProposedChangeActionButtonProps) => {
  const auth = useAuth();
  const { approve, cancelApprove } = usePcActionsContext();

  const proposedChangesDetails = useAtomValue(proposedChangedState);

  const hasApproved = auth.user && hasUserApprovedProposedChange(proposedChangesDetails, auth.user);

  const { mutate, isPending } = useUpdateProposedChangeReview({
    onSuccess: async () => {
      queryClient.invalidateQueries({
        predicate: (query) => query.queryKey.includes(proposedChangesDetails.id),
      });
      toast(
        <Alert
          type={ALERT_TYPES.SUCCESS}
          message={hasApproved ? "Proposed change approval canceled!" : "Proposed change approved!"}
        />
      );
    },
    onError: () => {
      toast(
        <Alert
          type={ALERT_TYPES.ERROR}
          message={
            hasApproved
              ? "An error occurred while canceling the approval"
              : "An error occurred while approving"
          }
        />
      );
    },
  });

  const handleAction = (event: React.MouseEvent<HTMLButtonElement>) => {
    event.stopPropagation();

    mutate({
      proposedChangeId: proposedChangesDetails.id,
      decision: hasApproved ? CANCEL_APPROVE_DECISION : APPROVE_DECISION,
    });
  };

  const tooltipContent = hasApproved
    ? cancelApprove.unavailability_reason
    : approve.unavailability_reason;
  const tooltipEnabled = hasApproved ? !cancelApprove.available : !approve.available;

  return (
    <>
      <Tooltip content={tooltipContent} enabled={tooltipEnabled} className="whitespace-pre">
        <Button
          className="flex h-full grow flex-wrap gap-2 rounded-r-none border-r-white"
          onClick={handleAction}
          variant={"primary"}
          isLoading={isPending}
          disabled={tooltipEnabled || isPending}
        >
          {hasApproved ? "Cancel Approve" : "Approve"}
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
        aria-label="More actions"
        type="button"
      >
        <Icon icon="mdi:unfold-more-horizontal" />
      </Button>
    </>
  );
};
