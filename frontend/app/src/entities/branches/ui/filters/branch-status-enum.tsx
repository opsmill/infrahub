import { AlertTriangleIcon, CheckCircleIcon, LoaderIcon } from "lucide-react";
import { forwardRef, useState } from "react";

import { Badge } from "@/shared/components/ui/badge";
import {
  Combobox,
  ComboboxContent,
  ComboboxItem,
  ComboboxList,
  ComboboxTrigger,
} from "@/shared/components/ui/combobox";
import { classNames } from "@/shared/utils/common";

import { BRANCH_STATUS, type BranchStatus } from "@/entities/branches/constants";

const pillStyle = "gap-1 rounded-full font-normal";

function BranchStatusOption({ status }: { status: BranchStatus }) {
  switch (status) {
    case BRANCH_STATUS.OPEN: {
      return (
        <Badge className={classNames(pillStyle)} variant="green">
          <CheckCircleIcon className="size-3" /> Open
        </Badge>
      );
    }
    case BRANCH_STATUS.NEED_REBASE: {
      return (
        <Badge className={classNames(pillStyle)} variant="yellow">
          <AlertTriangleIcon className="size-3" /> Rebase needed
        </Badge>
      );
    }
    case BRANCH_STATUS.NEED_UPGRADE_REBASE: {
      return (
        <Badge className={classNames(pillStyle)} variant="yellow">
          <AlertTriangleIcon className="size-3" /> Rebase needed (upgrade)
        </Badge>
      );
    }
    case BRANCH_STATUS.DELETING: {
      return (
        <Badge className={classNames(pillStyle)} variant="red">
          <LoaderIcon className="size-3" /> Deleting
        </Badge>
      );
    }
    default: {
      return null;
    }
  }
}

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
          {value ? <BranchStatusOption status={value} /> : null}
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
                <BranchStatusOption status={status} />
              </ComboboxItem>
            ))}
          </ComboboxList>
        </ComboboxContent>
      </Combobox>
    );
  }
);
