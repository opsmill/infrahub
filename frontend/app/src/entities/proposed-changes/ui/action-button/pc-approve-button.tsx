import { useAuth } from "@/entities/authentication/ui/useAuth";
import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import { Button } from "@/shared/components/buttons/button-primitive";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { Tooltip } from "@/shared/components/ui/tooltip";
import { Icon } from "@iconify-icon/react";
import { useAtomValue } from "jotai";
import { toast } from "react-toastify";
import { APPROVE_DECISION, CANCEL_APPROVE_DECISION } from "../../constants";
import { useUpdateProposedChangeReview } from "../../domain/update-review.mutation";
import { proposedChangedState } from "../../stores/proposedChanges.atom";
import { hasUserApprovedProposedChange } from "../../utils/has-user-approved-proposed-change";
import { usePcActionsContext } from "../pc-actions-permissions-context";
import { ProposedChangeActionButtonProps } from "./types";

export const ApproveButton = ({ setOpen }: ProposedChangeActionButtonProps) => {
  const auth = useAuth();
  const { approve } = usePcActionsContext();

  const proposedChangesDetails = useAtomValue(proposedChangedState);

  const hasApproved = auth.user && hasUserApprovedProposedChange(proposedChangesDetails, auth.user);

  const { mutate, isPending } = useUpdateProposedChangeReview({
    onSuccess: async () => {
      await graphqlClient.reFetchObservableQueries();
      toast(
        <Alert
          type={ALERT_TYPES.SUCCESS}
          message={hasApproved ? "Proposed change approval canceled!" : "Proposed change approved!"}
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

  return (
    <Tooltip content={approve.unavailability_reason} enabled={!approve.available}>
      <>
        <Button
          className="grow flex flex-wrap gap-2 h-full rounded-r-none border-r-white"
          onClick={handleAction}
          variant={"primary"}
          isLoading={isPending}
          disabled={!approve.available}
        >
          {hasApproved ? "Cancel Approve" : "Approve"}
        </Button>

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
    </Tooltip>
  );
};
