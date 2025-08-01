import { PROPOSED_CHANGES_OBJECT } from "@/config/constants";
import { useUpdateObjectMutation } from "@/entities/nodes/object/domain/update-object.mutation";
import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import { Button } from "@/shared/components/buttons/button-primitive";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { Tooltip } from "@/shared/components/ui/tooltip";
import { Icon } from "@iconify-icon/react";
import { useAtomValue } from "jotai";
import { toast } from "react-toastify";
import { proposedChangedState } from "../../stores/proposedChanges.atom";
import { usePcActionsContext } from "../pc-actions-permissions-context";
import { ProposedChangeActionButtonProps } from "./types";

export const DraftButton = ({ setOpen }: ProposedChangeActionButtonProps) => {
  const { setDraft } = usePcActionsContext();

  const proposedChangesDetails = useAtomValue(proposedChangedState);

  const isDraft = !!proposedChangesDetails.is_draft.value;

  const { mutate, isPending } = useUpdateObjectMutation({
    onSuccess: async () => {
      await graphqlClient.reFetchObservableQueries();
      toast(
        <Alert
          type={ALERT_TYPES.SUCCESS}
          message={isDraft ? "Proposed change opened!" : "Proposed change moved to draft!"}
        />
      );
    },
  });

  const handleAction = (event: React.MouseEvent<HTMLButtonElement>) => {
    event.stopPropagation();

    mutate({
      data: {
        id: proposedChangesDetails.id,
        is_draft: {
          value: !isDraft,
        },
      },
      objectKind: PROPOSED_CHANGES_OBJECT,
    });
  };

  return (
    <>
      <Tooltip content={setDraft.unavailability_reason} enabled={!setDraft.available}>
        <Button
          className="grow flex flex-wrap gap-2 h-full rounded-r-none border-r-white"
          onClick={handleAction}
          variant={"primary"}
          isLoading={isPending}
          disabled={!setDraft.available || isPending}
        >
          {isDraft ? "Open" : "Move to draft"}
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
