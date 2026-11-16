import { Button, Tooltip } from "@infrahub/ui";
import { toast } from "react-toastify";

import { queryClient } from "@/shared/api/rest/client";
import { Icon } from "@/shared/components/display/icon";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";

import { useAuth } from "@/entities/authentication/ui/auth-provider";
import {
  APPROVE_DECISION,
  CANCEL_APPROVE_DECISION,
} from "@/entities/proposed-changes/domain/model/proposed-change-review";
import { hasUserApprovedProposedChange } from "@/entities/proposed-changes/domain/rules/has-user-approved-proposed-change";
import { useProposedChange } from "@/entities/proposed-changes/ui/hooks/use-proposed-change";
import { usePcActionsContext } from "@/entities/proposed-changes/ui/pc-actions-permissions-context";
import { useUpdateProposedChangeReview } from "@/entities/proposed-changes/ui/queries/update-review.mutation";

import type { ProposedChangeActionButtonProps } from "./types";

export const ApproveButton = ({ setOpen }: ProposedChangeActionButtonProps) => {
  const auth = useAuth();
  const { approve, cancelApprove } = usePcActionsContext();

  const proposedChangesDetails = useProposedChange();

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
    onError: (error) => {
      toast(<Alert type={ALERT_TYPES.ERROR} message={error.message} />);
    },
  });

  const handleAction = () => {
    mutate({
      proposedChangeId: proposedChangesDetails.id,
      decision: hasApproved ? CANCEL_APPROVE_DECISION : APPROVE_DECISION,
    });
  };

  const tooltipMessage = hasApproved
    ? cancelApprove.unavailability_reason
    : approve.unavailability_reason;
  const isUnavailable = hasApproved ? !cancelApprove.available : !approve.available;

  return (
    <>
      <Tooltip message={isUnavailable ? tooltipMessage : undefined} className="whitespace-pre">
        <Button
          className="flex h-full grow flex-wrap gap-2 rounded-r-none"
          onPress={handleAction}
          variant={"primary"}
          isPending={isPending}
          isDisabled={isUnavailable || isPending}
          isDisabledAndFocusable={isUnavailable && !isPending}
        >
          {hasApproved ? "Cancel Approve" : "Approve"}
        </Button>
      </Tooltip>

      <Button
        className="h-full rounded-l-none border-l-0"
        variant={"primary"}
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
