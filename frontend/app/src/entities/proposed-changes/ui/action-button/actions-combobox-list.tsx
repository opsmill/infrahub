import { useAuth } from "@/entities/authentication/ui/useAuth";
import { ComboboxItem, ComboboxList } from "@/shared/components/ui/combobox";
import { useAtomValue } from "jotai";
import { forwardRef } from "react";
import { proposedChangedState } from "../../stores/proposedChanges.atom";
import { hasUserApproved } from "../../utils/has-user-approved";

type ActionItem = { value: string; name: string };

export interface ActionComboboxListProps {
  onSelect: (value: string) => void;
  value?: string | null;
}

export const ActionComboboxList = forwardRef<HTMLDivElement, ActionComboboxListProps>(
  ({ value, onSelect }, ref) => {
    const auth = useAuth();
    const proposedChangesDetails = useAtomValue(proposedChangedState);

    const actionsList: Record<string, ActionItem> = {
      approve: {
        value: "approve",
        name: hasUserApproved(proposedChangesDetails, auth.user) ? "Cancel Approval" : "Approve",
      },
      reject: {
        value: "reject",
        name: "Reject",
      },
      merge: {
        value: "merge",
        name: "Merge",
      },
      open: {
        value: "open",
        name: "Open",
      },
      close: {
        value: "close",
        name: "Close",
      },
    };

    return (
      <ComboboxList ref={ref}>
        {Object.entries(actionsList).map(([, action]) => {
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
