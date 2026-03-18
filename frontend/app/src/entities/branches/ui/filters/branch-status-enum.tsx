import { forwardRef, useState } from "react";

import {
  Combobox,
  ComboboxContent,
  ComboboxItem,
  ComboboxList,
  ComboboxTrigger,
} from "@/shared/components/ui/combobox";

import { BRANCH_STATUS, type BranchStatus } from "@/entities/branches/constants";
import { BranchStatusBadge } from "@/entities/branches/ui/branch-list-item/branch-status-badge";

export interface BranchStatusEnumProps {
  value: BranchStatus | null;
  onChange: (value: BranchStatus | null) => void;
  defaultOpen?: boolean;
}

export const BranchStatusEnum = forwardRef<HTMLButtonElement, BranchStatusEnumProps>(
  ({ value, onChange, defaultOpen = false }, ref) => {
    const [open, setOpen] = useState(defaultOpen);
    const items = Object.values(BRANCH_STATUS);

    return (
      <Combobox open={open} onOpenChange={setOpen}>
        <ComboboxTrigger ref={ref} className="min-w-[180px]">
          {value ? <BranchStatusBadge status={value} showOpen /> : null}
        </ComboboxTrigger>

        <ComboboxContent fitTriggerWidth={false}>
          <ComboboxList>
            {items.map((status) => (
              <ComboboxItem
                key={status}
                value={status}
                selectedValue={value ?? undefined}
                onSelect={() => {
                  onChange(status === value ? null : status);
                  setOpen(false);
                }}
              >
                <BranchStatusBadge status={status} showOpen />
              </ComboboxItem>
            ))}
          </ComboboxList>
        </ComboboxContent>
      </Combobox>
    );
  }
);
