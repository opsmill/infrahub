import { toast } from "react-toastify";

import { queryClient } from "@/shared/api/rest/client";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";

import { useUpdateObjectMutation } from "@/entities/nodes/object/ui/queries/update-object.mutation";
import { PROPOSED_CHANGE_OBJECT } from "@/entities/proposed-changes/domain/model/proposed-change";
import { CLOSE_STATE } from "@/entities/proposed-changes/domain/model/proposed-change-state";
import { PcSplitActionButton } from "@/entities/proposed-changes/ui/action-button/pc-split-action-button";
import { useProposedChange } from "@/entities/proposed-changes/ui/hooks/use-proposed-change";
import { usePcActionsContext } from "@/entities/proposed-changes/ui/pc-actions-permissions-context";

import type { ProposedChangeActionButtonProps } from "./types";

export const CloseButton = ({ setOpen }: ProposedChangeActionButtonProps) => {
  const { close } = usePcActionsContext();

  const proposedChangesDetails = useProposedChange();

  const { mutate, isPending } = useUpdateObjectMutation({
    onSuccess: async () => {
      queryClient.invalidateQueries({
        predicate: (query) => query.queryKey.includes(proposedChangesDetails.id),
      });
      toast(<Alert type={ALERT_TYPES.SUCCESS} message={"Proposed change closed!"} />);
    },
    onError: (error) => {
      toast(<Alert type={ALERT_TYPES.ERROR} message={error.message} />);
    },
  });

  const handleAction = () => {
    mutate({
      data: {
        id: proposedChangesDetails.id,
        state: {
          value: CLOSE_STATE,
        },
      },
      objectKind: PROPOSED_CHANGE_OBJECT,
    });
  };

  return (
    <PcSplitActionButton
      label="Close"
      variant={"danger"}
      onPress={handleAction}
      isPending={isPending}
      availability={close}
      onOpenMenu={() => {
        setOpen(true);
      }}
    />
  );
};
