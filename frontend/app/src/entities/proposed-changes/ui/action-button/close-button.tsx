import { PROPOSED_CHANGES_OBJECT } from "@/config/constants";
import { useUpdateObjectMutation } from "@/entities/nodes/object/domain/update-object.mutation";
import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import { Button } from "@/shared/components/buttons/button-primitive";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { Icon } from "@iconify-icon/react";
import { useAtomValue } from "jotai";
import { toast } from "react-toastify";
import { CLOSE_STATE } from "../../constant";
import { proposedChangedState } from "../../stores/proposedChanges.atom";
import { ProposedChangeActionButtonProps } from "./types";

export const OpenButton = ({ setOpen }: ProposedChangeActionButtonProps) => {
  const proposedChangesDetails = useAtomValue(proposedChangedState);

  const isClosed = proposedChangesDetails.state.value === "closed";

  const { mutateAsync, isPending } = useUpdateObjectMutation({
    onSuccess: async () => {
      await graphqlClient.reFetchObservableQueries();
      toast(<Alert type={ALERT_TYPES.SUCCESS} message={"Proposed change closed!"} />);
    },
  });

  const handleAction = (event: React.MouseEvent<HTMLButtonElement>) => {
    event.stopPropagation();

    return mutateAsync({
      data: {
        id: proposedChangesDetails.id,
        state: {
          value: CLOSE_STATE,
        },
      },
      objectKind: PROPOSED_CHANGES_OBJECT,
    });
  };

  return (
    <>
      <Button
        className="grow flex flex-wrap gap-2 h-full rounded-r-none border-r-white"
        onClick={handleAction}
        variant={"primary"}
        isLoading={isPending}
        disabled={isClosed || isPending}
      >
        Close
      </Button>

      <Button
        className="h-full rounded-l-none border-l-0"
        variant={"primary"}
        size={"sm"}
        onClick={() => {
          setOpen(true);
        }}
        disabled={isClosed || isPending}
      >
        <Icon icon="mdi:unfold-more-horizontal" />
      </Button>
    </>
  );
};
