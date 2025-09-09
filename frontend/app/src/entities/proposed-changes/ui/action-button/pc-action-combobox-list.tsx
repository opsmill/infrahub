import { useAtomValue } from "jotai";
import { forwardRef } from "react";

import { ComboboxItem, ComboboxList } from "@/shared/components/ui/combobox";
import { Tooltip } from "@/shared/components/ui/tooltip";

import { proposedChangedState } from "@/entities/proposed-changes/stores/proposedChanges.atom";
import { usePcActionsContext } from "@/entities/proposed-changes/ui/pc-actions-permissions-context";

type ActionItem = { value: string; name: string; isDisabled?: boolean; message: string | null };

export interface ActionComboboxListProps {
  onSelect: (value: string) => void;
  value?: string | null;
}

export const ActionComboboxList = forwardRef<HTMLDivElement, ActionComboboxListProps>(
  ({ value, onSelect }, ref) => {
    const { setDraft, unsetDraft, close, merge } = usePcActionsContext();
    const proposedChangesDetails = useAtomValue(proposedChangedState);

    const actionsList: Record<string, ActionItem> = {
      merge: {
        value: "merge",
        name: "Merge",
        isDisabled: !merge.available,
        message: merge.unavailability_reason,
      },
      close: {
        value: "close",
        name: "Close",
        isDisabled: !close.available,
        message: close.unavailability_reason,
      },
      draft: {
        value: "draft",
        name: proposedChangesDetails.is_draft?.value ? "Open" : "Move to draft",
        isDisabled: proposedChangesDetails.is_draft?.value
          ? !unsetDraft.available
          : !setDraft.available,
        message: proposedChangesDetails.is_draft?.value
          ? unsetDraft.unavailability_reason
          : setDraft.unavailability_reason,
      },
    };

    return (
      <ComboboxList ref={ref}>
        {Object.entries(actionsList).map(([, action]) => {
          if (action.isDisabled) {
            return (
              <Tooltip
                enabled
                content={action.message}
                className="whitespace-pre"
                key={action.value}
              >
                <span className="ml-5 flex cursor-default select-none items-center gap-2 truncate rounded-md px-2 py-1.5 text-sm opacity-50 outline-hidden">
                  {action.name}
                </span>
              </Tooltip>
            );
          }

          return (
            <ComboboxItem
              key={action.value}
              value={action.value}
              selectedValue={value}
              onSelect={() => onSelect(action.value)}
              className="cursor-pointer"
            >
              <span className="truncate">{action.name}</span>
            </ComboboxItem>
          );
        })}
      </ComboboxList>
    );
  }
);
