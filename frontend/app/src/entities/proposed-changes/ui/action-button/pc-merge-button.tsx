import { PROPOSED_CHANGES_OBJECT } from "@/config/constants";
import { useUpdateObjectMutation } from "@/entities/nodes/object/domain/update-object.mutation";
import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import { Button } from "@/shared/components/buttons/button-primitive";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { Tooltip } from "@/shared/components/ui/tooltip";
import { Icon } from "@iconify-icon/react";
import { useAtomValue } from "jotai";
import { toast } from "react-toastify";
import { MERGE_STATE } from "../../constants";
import { proposedChangedState } from "../../stores/proposedChanges.atom";
import { usePcActionsContext } from "../pc-actions-permissions-context";
import { ProposedChangeActionButtonProps } from "./types";

export const MergeButton = ({ setOpen }: ProposedChangeActionButtonProps) => {
  const { merge } = usePcActionsContext();

  const proposedChangesDetails = useAtomValue(proposedChangedState);

  const { mutate, isPending } = useUpdateObjectMutation({
    onSuccess: async () => {
      await graphqlClient.reFetchObservableQueries();
      toast(<Alert type={ALERT_TYPES.SUCCESS} message={"Proposed change merged!"} />);
    },
  });

  const handleAction = (event: React.MouseEvent<HTMLButtonElement>) => {
    event.stopPropagation();

    mutate({
      data: {
        id: proposedChangesDetails.id,
        state: {
          value: MERGE_STATE,
        },
      },
      objectKind: PROPOSED_CHANGES_OBJECT,
    });
  };

  return (
    <Tooltip content={merge.unavailability_reason} enabled={!merge.available}>
      <>
        <Button
          className="grow flex flex-wrap gap-2 h-full rounded-r-none border-r-white"
          onClick={handleAction}
          variant={"primary"}
          isLoading={isPending}
          disabled={!merge.available || isPending}
        >
          Merge
        </Button>

        <Button
          className="h-full rounded-l-none border-l-0"
          variant={"primary"}
          size={"sm"}
          onClick={() => {
            setOpen(true);
          }}
          disabled={!merge.available || isPending}
          data-testid="proposed-change-action-button-select"
        >
          <Icon icon="mdi:unfold-more-horizontal" />
        </Button>
      </>
    </Tooltip>
  );
};
