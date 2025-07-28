import { pcStatesList } from "@/entities/proposed-changes/constants";
import { ComboboxItem, ComboboxList } from "@/shared/components/ui/combobox";
import { forwardRef } from "react";

export interface StateComboboxListProps {
  onSelect: (value: string) => void;
  value?: string | null;
}

export const StateComboboxList = forwardRef<HTMLDivElement, StateComboboxListProps>(
  ({ value, onSelect }, ref) => {
    return (
      <ComboboxList ref={ref}>
        {Object.entries(pcStatesList).map(([, state]) => {
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
