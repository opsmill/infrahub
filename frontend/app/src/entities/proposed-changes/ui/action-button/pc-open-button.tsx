import { PROPOSED_CHANGES_OBJECT } from "@/config/constants";
import { useUpdateObjectMutation } from "@/entities/nodes/object/domain/update-object.mutation";
import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import { Button } from "@/shared/components/buttons/button-primitive";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { Tooltip } from "@/shared/components/ui/tooltip";
import { Icon } from "@iconify-icon/react";
import { useAtomValue } from "jotai";
import { toast } from "react-toastify";
import { CLOSE_STATE } from "../../constants";
import { proposedChangedState } from "../../stores/proposedChanges.atom";
import { usePcActionsContext } from "../pc-actions-permissions-context";
import { ProposedChangeActionButtonProps } from "./types";

export const OpenButton = ({ setOpen }: ProposedChangeActionButtonProps) => {
  const { open } = usePcActionsContext();

  const proposedChangesDetails = useAtomValue(proposedChangedState);

  const { mutate, isPending } = useUpdateObjectMutation({
    onSuccess: async () => {
      await graphqlClient.reFetchObservableQueries();
      toast(<Alert type={ALERT_TYPES.SUCCESS} message={"Proposed change closed!"} />);
    },
  });

  const handleAction = (event: React.MouseEvent<HTMLButtonElement>) => {
    event.stopPropagation();

    mutate({
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
    <Tooltip content={open.unavailability_reason} enabled={!open.available}>
      <>
        <Button
          className="grow flex flex-wrap gap-2 h-full rounded-r-none border-r-white"
          onClick={handleAction}
          variant={"primary"}
          isLoading={isPending}
          disabled={!open.available || isPending}
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
          disabled={!open.available || isPending}
          data-testid="proposed-change-action-button-select"
        >
          <Icon icon="mdi:unfold-more-horizontal" />
        </Button>
      </>
    </Tooltip>
  );
};
