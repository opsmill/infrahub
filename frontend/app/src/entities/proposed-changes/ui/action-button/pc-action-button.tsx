import type { ComponentType } from "react";

import {
  type PcActionComboboxItem,
  PcActionComboboxList,
} from "@/entities/proposed-changes/ui/action-button/pc-action-combobox-list";
import {
  PcActionPicker,
  type PcActionPickerListProps,
} from "@/entities/proposed-changes/ui/action-button/pc-action-picker";
import { CloseButton } from "@/entities/proposed-changes/ui/action-button/pc-close-button";
import { DraftButton } from "@/entities/proposed-changes/ui/action-button/pc-draft-button";
import { MergeButton } from "@/entities/proposed-changes/ui/action-button/pc-merge-button";
import type { ProposedChangeActionButtonProps } from "@/entities/proposed-changes/ui/action-button/types";
import { useProposedChange } from "@/entities/proposed-changes/ui/hooks/use-proposed-change";
import {
  PcActionsContext,
  usePcActionsContext,
} from "@/entities/proposed-changes/ui/pc-actions-permissions-context";
import { useGetProposedChangeAvailableActions } from "@/entities/proposed-changes/ui/queries/get-proposed-change-available-actions.query";

type Action = "merge" | "close" | "draft";

const actionButtons: Record<Action, ComponentType<ProposedChangeActionButtonProps>> = {
  merge: MergeButton,
  close: CloseButton,
  draft: DraftButton,
};

const ActionComboboxList = ({ value, onSelect }: PcActionPickerListProps<Action>) => {
  const { setDraft, unsetDraft, close, merge } = usePcActionsContext();
  const proposedChangesDetails = useProposedChange();

  const items: PcActionComboboxItem<Action>[] = [
    { value: "merge", name: "Merge", availability: merge },
    { value: "close", name: "Close", availability: close },
    {
      value: "draft",
      name: proposedChangesDetails.is_draft?.value ? "Open" : "Move to draft",
      availability: proposedChangesDetails.is_draft?.value ? unsetDraft : setDraft,
    },
  ];

  return <PcActionComboboxList items={items} value={value} onSelect={onSelect} />;
};

export const PcActionButton = () => {
  const proposedChange = useProposedChange();

  const { data, isPending } = useGetProposedChangeAvailableActions({
    proposedChangeId: proposedChange.id,
  });

  return (
    <PcActionsContext value={data}>
      <PcActionPicker
        isLoading={isPending}
        defaultAction="merge"
        buttons={actionButtons}
        list={ActionComboboxList}
      />
    </PcActionsContext>
  );
};
