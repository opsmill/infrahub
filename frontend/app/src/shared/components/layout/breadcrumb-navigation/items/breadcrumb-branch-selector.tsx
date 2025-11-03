import { Icon } from "@iconify-icon/react";
import { ChevronsUpDownIcon } from "lucide-react";
import { useFilter } from "react-aria-components";

import { constructPath } from "@/shared/api/rest/fetch";
import { Autocomplete } from "@/shared/components/aria/autocomplete";
import { ListBox, ListBoxItem } from "@/shared/components/aria/list-box";
import { Popover, PopoverDialog, PopoverTrigger } from "@/shared/components/aria/popover";
import { BreadcrumbItem } from "@/shared/components/ui/breadcrumb";

import { useGetBranches } from "@/entities/branches/domain/get-branches.query";

interface BreadcrumbBranchSelectorProps {
  currentBranchName: string;
}

export default function BreadcrumbBranchSelector({
  currentBranchName,
  ...props
}: BreadcrumbBranchSelectorProps) {
  const { data: branches } = useGetBranches();
  let { contains } = useFilter({ sensitivity: "base" });

  return (
    <PopoverTrigger>
      <BreadcrumbItem {...props}>
        <span className="truncate">{currentBranchName}</span>
        <ChevronsUpDownIcon className="ml-2 size-4" />
      </BreadcrumbItem>

      <Popover className="bg-stone-100/50 backdrop-blur">
        <PopoverDialog aria-label="Branch selector">
          {({ close }) => (
            <Autocomplete filter={contains}>
              <ListBox
                items={branches}
                emptyMessage="No branches found."
                className="space-y-0"
                onAction={close}
              >
                {(branch) => (
                  <ListBoxItem
                    textValue={branch.name}
                    href={constructPath(`/branches/${branch.name}`)}
                  >
                    <Icon icon="mdi:source-branch" /> {branch.name}
                  </ListBoxItem>
                )}
              </ListBox>
            </Autocomplete>
          )}
        </PopoverDialog>
      </Popover>
    </PopoverTrigger>
  );
}
