import { ComboboxItem, ComboboxList } from "@/shared/components/ui/combobox";
import { forwardRef } from "react";

type ActionItem = { value: string; name: string };

const actionsList: Record<string, ActionItem> = {
  approve: {
    value: "approve",
    name: "Approve",
  },
  "cancel-approve": {
    value: "cancel-approve",
    name: "Cancel approval",
  },
  reject: {
    value: "reject",
    name: "Reject",
  },
  "cancel-reject": {
    value: "cancel-reject",
    name: "Cancel reject",
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

export interface ActionComboboxListProps {
  onSelect: (value: ActionItem) => void;
  value?: string | null;
}

export const ActionComboboxList = forwardRef<HTMLDivElement, ActionComboboxListProps>(
  ({ value, onSelect }, ref) => {
    return (
      <ComboboxList ref={ref}>
        {Object.entries(actionsList).map(([, action]) => {
          return (
            <ComboboxItem
              key={action.value}
              value={action.value}
              selectedValue={value}
              onSelect={() => onSelect(action)}
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
