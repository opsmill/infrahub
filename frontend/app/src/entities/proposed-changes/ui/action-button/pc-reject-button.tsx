import { Icon } from "@iconify-icon/react";
import { Button, Tooltip } from "@infrahub/ui";
import { toast } from "react-toastify";

import { queryClient } from "@/shared/api/rest/client";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";

import { useAuth } from "@/entities/authentication/ui/useAuth";
import { CANCEL_REJECT_DECISION, REJECT_DECISION } from "@/entities/proposed-changes/constants";
import type { ProposedChangeActionButtonProps } from "@/entities/proposed-changes/ui/action-button/types";
import { useProposedChange } from "@/entities/proposed-changes/ui/hooks/use-proposed-change";
import { usePcActionsContext } from "@/entities/proposed-changes/ui/pc-actions-permissions-context";
import { useUpdateProposedChangeReview } from "@/entities/proposed-changes/ui/queries/update-review.mutation";
import { hasUserRejectedProposedChange } from "@/entities/proposed-changes/utils/has-user-rejected-proposed-change";

export const RejectButton = ({ setOpen }: ProposedChangeActionButtonProps) => {
  const auth = useAuth();
  const { reject, cancelReject } = usePcActionsContext();
  const proposedChangesDetails = useProposedChange();

  const hasRejected = auth.user && hasUserRejectedProposedChange(proposedChangesDetails, auth.user);

  const { mutate, isPending } = useUpdateProposedChangeReview({
    onSuccess: async () => {
      queryClient.invalidateQueries({
        predicate: (query) => query.queryKey.includes(proposedChangesDetails.id),
      });
      toast(
        <Alert
          type={ALERT_TYPES.SUCCESS}
          message={hasRejected ? "Proposed change reject canceled!" : "Proposed change rejected!"}
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
      decision: hasRejected ? CANCEL_REJECT_DECISION : REJECT_DECISION,
    });
  };

  const tooltipMessage = hasRejected
    ? cancelReject.unavailability_reason
    : reject.unavailability_reason;
  const isUnavailable = hasRejected ? !cancelReject.available : !reject.available;

  return (
    <>
      <Tooltip message={isUnavailable ? tooltipMessage : undefined} className="whitespace-pre">
        <Button
          className="flex h-full grow flex-wrap gap-2 rounded-r-none border-r-white"
          onPress={handleAction}
          variant={"primary"}
          isPending={isPending}
          isDisabled={isUnavailable || isPending}
          isDisabledAndFocusable={isUnavailable && !isPending}
        >
          {hasRejected ? "Cancel Reject" : "Reject"}
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
