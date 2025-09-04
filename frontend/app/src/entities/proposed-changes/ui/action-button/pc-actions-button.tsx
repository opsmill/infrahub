import { useAtomValue } from "jotai";
import { ReactElement, useState } from "react";

import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { Combobox, ComboboxContent } from "@/shared/components/ui/combobox";
import { PopoverTrigger } from "@/shared/components/ui/popover";
import { inputStyle } from "@/shared/components/ui/style";
import { classNames } from "@/shared/utils/common";

import { useAuth } from "@/entities/authentication/ui/useAuth";
import { useGetProposedChangeAvailableActions } from "@/entities/proposed-changes/domain/get-proposed-change-available-actions.query";
import { proposedChangedState } from "@/entities/proposed-changes/stores/proposedChanges.atom";
import { ActionComboboxList } from "@/entities/proposed-changes/ui/action-button/pc-actions-combobox-list";
import { ApproveButton } from "@/entities/proposed-changes/ui/action-button/pc-approve-button";
import { CloseButton } from "@/entities/proposed-changes/ui/action-button/pc-close-button";
import { DraftButton } from "@/entities/proposed-changes/ui/action-button/pc-draft-button";
import { MergeButton } from "@/entities/proposed-changes/ui/action-button/pc-merge-button";
import { PcPlaceholderButton } from "@/entities/proposed-changes/ui/action-button/pc-placeholder-button";
import { RejectButton } from "@/entities/proposed-changes/ui/action-button/pc-reject-button";
import { ProposedChangeActionButtonProps } from "@/entities/proposed-changes/ui/action-button/types";
import { PcActionsContext } from "@/entities/proposed-changes/ui/pc-actions-permissions-context";

type ActionButtonComponent = (props: ProposedChangeActionButtonProps) => ReactElement;

type Action = "approve" | "reject" | "merge" | "close" | "draft";

const actionsListMapping: Record<Action, ActionButtonComponent> = {
  approve: ({ setOpen }) => <ApproveButton setOpen={setOpen} />,
  reject: ({ setOpen }) => <RejectButton setOpen={setOpen} />,
  merge: ({ setOpen }) => <MergeButton setOpen={setOpen} />,
  close: ({ setOpen }) => <CloseButton setOpen={setOpen} />,
  draft: ({ setOpen }) => <DraftButton setOpen={setOpen} />,
};

export const PcActionButton = () => {
  const auth = useAuth();
  const proposedChange = useAtomValue(proposedChangedState);

  const { data, isPending } = useGetProposedChangeAvailableActions({
    proposedChangeId: proposedChange.id,
  });

  const [open, setOpen] = useState(false);
  const [action, setAction] = useState<Action>("merge");

  return (
    <PcActionsContext value={data}>
      <Combobox open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <div className={classNames(inputStyle, "flex p-0 border-0 w-40")}>
            {isPending && <LoadingIndicator />}
            {!isPending && auth?.user?.id ? (
              actionsListMapping?.[action]?.({ setOpen })
            ) : (
              <PcPlaceholderButton />
            )}
          </div>
        </PopoverTrigger>
        <ComboboxContent fitTriggerWidth={false}>
          <ActionComboboxList
            value={action}
            onSelect={(action) => {
              setOpen(false);
              setAction(action as Action);
            }}
          />
        </ComboboxContent>
      </Combobox>
    </PcActionsContext>
  );
};
