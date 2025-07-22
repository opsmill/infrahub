import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import { Button } from "@/shared/components/buttons/button-primitive";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { Icon } from "@iconify-icon/react";
import { useAtomValue } from "jotai";
import { toast } from "react-toastify";
import { APPROVE_DECISION } from "../../constant";
import { useUpdateReview } from "../../domain/update-review.mutation";
import { proposedChangedState } from "../../stores/proposedChanges.atom";
import { ProposedChangeActionButtonProps } from "./types";

export const RejectButton = ({ setOpen }: ProposedChangeActionButtonProps) => {
  const proposedChangesDetails = useAtomValue(proposedChangedState);

  const { mutateAsync, isPending } = useUpdateReview({
    onSuccess: async () => {
      await graphqlClient.reFetchObservableQueries();
      toast(<Alert type={ALERT_TYPES.SUCCESS} message={"Proposed change approved!"} />);
    },
  });

  const handleAction = (event) => {
    event.stopPropagation();

    mutateAsync({
      proposedChangeId: proposedChangesDetails.id,
      decision: APPROVE_DECISION,
    });
  };

  return (
    <>
      <Button
        className="grow flex flex-wrap gap-2 h-full rounded-r-none border-r-white"
        onClick={handleAction}
        variant={"primary"}
        isLoading={isPending}
        disabled={isPending}
      >
        Reject
      </Button>

      <Button
        className="h-full rounded-l-none border-l-0"
        variant={"primary"}
        size={"sm"}
        onClick={() => {
          setOpen(true);
        }}
        disabled={isPending}
      >
        <Icon icon="mdi:unfold-more-horizontal" />
      </Button>
    </>
  );
};
