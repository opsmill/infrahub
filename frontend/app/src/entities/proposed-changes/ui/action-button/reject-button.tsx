import { useAuth } from "@/entities/authentication/ui/useAuth";
import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import { Button } from "@/shared/components/buttons/button-primitive";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { Icon } from "@iconify-icon/react";
import { useAtomValue } from "jotai";
import { toast } from "react-toastify";
import { CANCEL_REJECT_DECISION, REJECT_DECISION } from "../../constants";
import { useUpdateProposedChangeReview } from "../../domain/update-review.mutation";
import { proposedChangedState } from "../../stores/proposedChanges.atom";
import { hasUserRejectedProposedChange } from "../../utils/has-user-rejected-proposed-change";
import { ProposedChangeActionButtonProps } from "./types";

export const RejectButton = ({ setOpen }: ProposedChangeActionButtonProps) => {
  const auth = useAuth();
  const proposedChangesDetails = useAtomValue(proposedChangedState);

  const isMerged = proposedChangesDetails.state.value === "merged";
  const isClosed = proposedChangesDetails.state.value === "closed";
  const hasApproved = auth.user && hasUserRejectedProposedChange(proposedChangesDetails, auth.user);

  const { mutateAsync, isPending } = useUpdateProposedChangeReview({
    onSuccess: async () => {
      await graphqlClient.reFetchObservableQueries();
      toast(
        <Alert
          type={ALERT_TYPES.SUCCESS}
          message={hasApproved ? "Proposed change reject canceled!" : "Proposed change rejected!"}
        />
      );
    },
  });

  const handleAction = (event: React.MouseEvent<HTMLButtonElement>) => {
    event.stopPropagation();

    mutateAsync({
      proposedChangeId: proposedChangesDetails.id,
      decision: hasApproved ? CANCEL_REJECT_DECISION : REJECT_DECISION,
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
        {hasApproved ? "Cancel Reject" : "Reject"}
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
