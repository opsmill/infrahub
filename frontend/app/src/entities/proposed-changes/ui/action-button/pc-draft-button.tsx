import { toast } from "react-toastify";

import { queryClient } from "@/shared/api/rest/client";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";

import { useUpdateObjectMutation } from "@/entities/nodes/object/ui/queries/update-object.mutation";
import { PROPOSED_CHANGE_OBJECT } from "@/entities/proposed-changes/domain/model/proposed-change";
import { PcSplitActionButton } from "@/entities/proposed-changes/ui/action-button/pc-split-action-button";
import { useProposedChange } from "@/entities/proposed-changes/ui/hooks/use-proposed-change";
import { usePcActionsContext } from "@/entities/proposed-changes/ui/pc-actions-permissions-context";

import type { ProposedChangeActionButtonProps } from "./types";

export const DraftButton = ({ setOpen }: ProposedChangeActionButtonProps) => {
  const { setDraft, unsetDraft } = usePcActionsContext();

  const proposedChangesDetails = useProposedChange();

  const isDraft = !!proposedChangesDetails.is_draft.value;

  const { mutate, isPending } = useUpdateObjectMutation({
    onSuccess: async () => {
      queryClient.invalidateQueries({
        predicate: (query) => query.queryKey.includes(proposedChangesDetails.id),
      });
      toast(
        <Alert
          type={ALERT_TYPES.SUCCESS}
          message={isDraft ? "Proposed change opened!" : "Proposed change moved to draft!"}
        />
      );
    },
    onError: (error) => {
      toast(<Alert type={ALERT_TYPES.ERROR} message={error.message} />);
    },
  });

  const handleAction = () => {
    mutate({
      data: {
        id: proposedChangesDetails.id,
        is_draft: {
          value: !isDraft,
        },
      },
      objectKind: PROPOSED_CHANGE_OBJECT,
    });
  };

  return (
    <PcSplitActionButton
      label={isDraft ? "Open" : "Move to draft"}
      variant={"outline"}
      onPress={handleAction}
      isPending={isPending}
      availability={isDraft ? unsetDraft : setDraft}
      onOpenMenu={() => {
        setOpen(true);
      }}
    />
  );
};
