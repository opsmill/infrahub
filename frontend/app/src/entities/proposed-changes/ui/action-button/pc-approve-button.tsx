import { useAuth } from "@/entities/authentication/ui/useAuth";
import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import { Button } from "@/shared/components/buttons/button-primitive";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { Icon } from "@iconify-icon/react";
import { useAtomValue } from "jotai";
import { toast } from "react-toastify";
import { APPROVE_DECISION, CANCEL_APPROVE_DECISION } from "../../constants";
import { useUpdateProposedChangeReview } from "../../domain/update-review.mutation";
import { proposedChangedState } from "../../stores/proposedChanges.atom";
import { hasUserApprovedProposeChange } from "../../utils/has-user-approved-proposed-change";
import { ProposedChangeActionButtonProps } from "./types";

export const ApproveButton = ({ setOpen }: ProposedChangeActionButtonProps) => {
  const auth = useAuth();
  const proposedChangesDetails = useAtomValue(proposedChangedState);

  const isMerged = proposedChangesDetails.state.value === "merged";
  const isClosed = proposedChangesDetails.state.value === "closed";
  const hasApproved = auth.user && hasUserApprovedProposeChange(proposedChangesDetails, auth.user);

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
    <>
      <Button
        className="grow flex flex-wrap gap-2 h-full rounded-r-none border-r-white"
        onClick={handleAction}
        variant={"primary"}
        isLoading={isPending}
        disabled={isMerged || isClosed || isPending}
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
        disabled={isMerged || isClosed || isPending}
        data-testid="proposed-change-action-button-select"
      >
        <Icon icon="mdi:unfold-more-horizontal" />
      </Button>
    </>
  );
};
