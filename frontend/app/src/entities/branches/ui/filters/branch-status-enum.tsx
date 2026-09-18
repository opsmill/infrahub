import React from "react";

import { BranchStatus } from "@/shared/api/graphql/generated/types";
import {
  Combobox,
  ComboboxContent,
  ComboboxItem,
  ComboboxList,
  ComboboxTrigger,
} from "@/shared/components/ui/combobox";

import { BranchStatusBadge } from "@/entities/branches/ui/branch-list-item/branch-status-badge";

export const ALL_BRANCH_STATUSES: readonly BranchStatus[] = Object.values(BranchStatus);

export interface BranchStatusEnumProps<TStatus extends BranchStatus> {
  ref?: React.Ref<HTMLButtonElement>;
  value: TStatus | null;
  onChange: (value: TStatus | null) => void;
  defaultOpen?: boolean;
  options: readonly TStatus[];
  placeholder?: string;
  "aria-label"?: string;
}

export const BranchStatusEnum = <TStatus extends BranchStatus>({
  ref,
  value,
  onChange,
  defaultOpen = false,
  options,
  placeholder,
  "aria-label": ariaLabel,
}: BranchStatusEnumProps<TStatus>) => {
  const [open, setOpen] = React.useState(defaultOpen);

  return (
    <Combobox open={open} onOpenChange={setOpen}>
      <ComboboxTrigger aria-label={ariaLabel} ref={ref} className="min-w-[180px]">
        {value ? (
          <BranchStatusBadge status={value} showOpen />
        ) : (
          <span className="text-subtle-muted">{placeholder}</span>
        )}
      </ComboboxTrigger>

      <ComboboxContent fitTriggerWidth={false}>
        <ComboboxList>
          {options.map((status) => (
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
};
