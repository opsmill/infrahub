import { useAtomValue } from "jotai";
import { type ReactElement, useState } from "react";

import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { Combobox, ComboboxContent } from "@/shared/components/ui/combobox";
import { PopoverTrigger } from "@/shared/components/ui/popover";
import { inputStyle } from "@/shared/components/ui/style";
import { classNames } from "@/shared/utils/common";

import { useAuth } from "@/entities/authentication/ui/useAuth";
import { useGetProposedChangeAvailableActions } from "@/entities/proposed-changes/ui/queries/get-proposed-change-available-actions.query";
import { proposedChangedState } from "@/entities/proposed-changes/stores/proposedChanges.atom";
import { ActionComboboxList } from "@/entities/proposed-changes/ui/action-button/pc-action-combobox-list";
import { CloseButton } from "@/entities/proposed-changes/ui/action-button/pc-close-button";
import { DraftButton } from "@/entities/proposed-changes/ui/action-button/pc-draft-button";
import { MergeButton } from "@/entities/proposed-changes/ui/action-button/pc-merge-button";
import { PcPlaceholderButton } from "@/entities/proposed-changes/ui/action-button/pc-placeholder-button";
import type { ProposedChangeActionButtonProps } from "@/entities/proposed-changes/ui/action-button/types";
import { PcActionsContext } from "@/entities/proposed-changes/ui/pc-actions-permissions-context";

type ActionButtonComponent = (props: ProposedChangeActionButtonProps) => ReactElement;

type Action = "merge" | "close" | "draft";

const actionsListMapping: Record<Action, ActionButtonComponent> = {
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
          <div className={classNames(inputStyle, "flex border-0 p-0")}>
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
