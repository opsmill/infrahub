import { toast } from "react-toastify";

import { queryClient } from "@/shared/api/rest/client";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";

import { useAuth } from "@/entities/authentication/ui/auth-provider";
import {
  APPROVE_DECISION,
  CANCEL_APPROVE_DECISION,
} from "@/entities/proposed-changes/domain/model/proposed-change-review";
import { hasUserApprovedProposedChange } from "@/entities/proposed-changes/domain/rules/has-user-approved-proposed-change";
import { PcSplitActionButton } from "@/entities/proposed-changes/ui/action-button/pc-split-action-button";
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

  return (
    <PcSplitActionButton
      label={hasApproved ? "Cancel Approve" : "Approve"}
      variant={"primary"}
      onPress={handleAction}
      isPending={isPending}
      availability={hasApproved ? cancelApprove : approve}
      onOpenMenu={() => {
        setOpen(true);
      }}
    />
  );
};
