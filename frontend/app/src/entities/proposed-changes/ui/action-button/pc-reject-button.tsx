import { useAuth } from "@/entities/authentication/ui/useAuth";
import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import { Button } from "@/shared/components/buttons/button-primitive";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { Tooltip } from "@/shared/components/ui/tooltip";
import { Icon } from "@iconify-icon/react";
import { useAtomValue } from "jotai";
import { toast } from "react-toastify";
import { CANCEL_REJECT_DECISION, REJECT_DECISION } from "../../constants";
import { useUpdateProposedChangeReview } from "../../domain/update-review.mutation";
import { proposedChangedState } from "../../stores/proposedChanges.atom";
import { hasUserRejectedProposedChange } from "../../utils/has-user-rejected-proposed-change";
import { usePcActionsContext } from "../pc-actions-permissions-context";
import { ProposedChangeActionButtonProps } from "./types";

export const RejectButton = ({ setOpen }: ProposedChangeActionButtonProps) => {
  const auth = useAuth();
  const { reject, cancelReject } = usePcActionsContext();
  const proposedChangesDetails = useAtomValue(proposedChangedState);

  const hasRejected = auth.user && hasUserRejectedProposedChange(proposedChangesDetails, auth.user);

  const { mutate, isPending } = useUpdateProposedChangeReview({
    onSuccess: async () => {
      await graphqlClient.reFetchObservableQueries();
      toast(
        <Alert
          type={ALERT_TYPES.SUCCESS}
          message={hasRejected ? "Proposed change reject canceled!" : "Proposed change rejected!"}
        />
      );
    },
  });

  const handleAction = (event: React.MouseEvent<HTMLButtonElement>) => {
    event.stopPropagation();

    mutate({
      proposedChangeId: proposedChangesDetails.id,
      decision: hasRejected ? CANCEL_REJECT_DECISION : REJECT_DECISION,
    });
  };

  const tooltipContent = hasRejected
    ? cancelReject.unavailability_reason
    : reject.unavailability_reason;
  const tooltipEnabled = hasRejected ? !cancelReject.available : !reject.available;

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
          {hasRejected ? "Cancel Reject" : "Reject"}
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
