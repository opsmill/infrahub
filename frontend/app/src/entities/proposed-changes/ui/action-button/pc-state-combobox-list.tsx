import { ComboboxItem, ComboboxList } from "@/shared/components/ui/combobox";
import { forwardRef } from "react";

type StateItem = { value: string; name: string; message: string };

export interface StateComboboxListProps {
  onSelect: (value: string) => void;
  value?: string | null;
}

export const statesList: Record<string, StateItem> = {
  open: {
    value: "open",
    name: "Open",
    message: "Open",
  },
  draft: {
    value: "draft",
    name: "Draft",
    message: "Open a draft",
  },
};

export const StateComboboxList = forwardRef<HTMLDivElement, StateComboboxListProps>(
  ({ value, onSelect }, ref) => {
    return (
      <ComboboxList ref={ref}>
        {Object.entries(statesList).map(([, state]) => {
          return (
            <ComboboxItem
              key={state.value}
              value={state.value}
              selectedValue={value}
              onSelect={() => onSelect(state.value)}
              className="cursor-pointer"
            >
              <span className="truncate">{state.name}</span>
            </ComboboxItem>
          );
        })}
      </ComboboxList>
    );
  }
);
