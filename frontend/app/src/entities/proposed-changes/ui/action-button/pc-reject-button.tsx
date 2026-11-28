import { toast } from "react-toastify";

import { queryClient } from "@/shared/api/rest/client";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";

import { useAuth } from "@/entities/authentication/ui/auth-provider";
import {
  CANCEL_REJECT_DECISION,
  REJECT_DECISION,
} from "@/entities/proposed-changes/domain/model/proposed-change-review";
import { hasUserRejectedProposedChange } from "@/entities/proposed-changes/domain/rules/has-user-rejected-proposed-change";
import { PcSplitActionButton } from "@/entities/proposed-changes/ui/action-button/pc-split-action-button";
import type { ProposedChangeActionButtonProps } from "@/entities/proposed-changes/ui/action-button/types";
import { useProposedChange } from "@/entities/proposed-changes/ui/hooks/use-proposed-change";
import { usePcActionsContext } from "@/entities/proposed-changes/ui/pc-actions-permissions-context";
import { useUpdateProposedChangeReview } from "@/entities/proposed-changes/ui/queries/update-review.mutation";

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

  return (
    <PcSplitActionButton
      label={hasRejected ? "Cancel Reject" : "Reject"}
      variant={"primary"}
      onPress={handleAction}
      isPending={isPending}
      availability={hasRejected ? cancelReject : reject}
      onOpenMenu={() => {
        setOpen(true);
      }}
    />
  );
};
