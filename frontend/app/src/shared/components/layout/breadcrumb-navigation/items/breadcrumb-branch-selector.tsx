import { Icon } from "@iconify-icon/react";
import { ChevronsUpDownIcon } from "lucide-react";
import { useFilter } from "react-aria-components";

import { constructPath } from "@/shared/api/rest/fetch";
import { Autocomplete } from "@/shared/components/aria/autocomplete";
import { Button } from "@/shared/components/aria/button";
import { ListBox, ListBoxItem } from "@/shared/components/aria/list-box";
import { MenuTrigger } from "@/shared/components/aria/menu";
import { Popover, PopoverDialog } from "@/shared/components/aria/popover";

import { useGetBranches } from "@/entities/branches/domain/get-branches.query";

interface BreadcrumbBranchSelectorProps {
  currentBranchName: string;
}

export default function BreadcrumbBranchSelector({
  currentBranchName,
  ...props
}: BreadcrumbBranchSelectorProps) {
  const { data: branches = [] } = useGetBranches();
  const { contains } = useFilter({ sensitivity: "base" });

  return (
    <MenuTrigger>
      <Button variant="ghost" {...props}>
        <span className="truncate">{currentBranchName}</span>
        <ChevronsUpDownIcon className="size-4" />
      </Button>

      <Popover className="bg-stone-100/50 backdrop-blur">
        <PopoverDialog aria-label="Branch selector">
          {({ close }) => (
            <Autocomplete filter={contains}>
              <ListBox
                items={branches}
                emptyMessage="No branches found."
                className="p-1"
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
    </MenuTrigger>
  );
}
