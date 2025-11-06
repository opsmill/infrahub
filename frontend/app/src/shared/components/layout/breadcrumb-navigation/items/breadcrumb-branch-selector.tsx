import { Icon } from "@iconify-icon/react";
import { useFilter } from "react-aria-components";

import { constructPath } from "@/shared/api/rest/fetch";
import { Autocomplete } from "@/shared/components/aria/autocomplete";
import { ListBox, ListBoxItem } from "@/shared/components/aria/list-box";
import { MenuTrigger } from "@/shared/components/aria/menu";
import { Popover, PopoverDialog } from "@/shared/components/aria/popover";
import { BreadcrumbItemTrigger } from "@/shared/components/layout/breadcrumb-navigation/items/breadcrumb-item-trigger";

import { useGetBranches } from "@/entities/branches/domain/get-branches.query";

interface BreadcrumbBranchSelectorProps {
  currentBranchName: string;
}

export default function BreadcrumbBranchSelector({
  currentBranchName,
}: BreadcrumbBranchSelectorProps) {
  const { data: branches = [] } = useGetBranches();
  const { contains } = useFilter({ sensitivity: "base" });

  return (
    <MenuTrigger>
      <BreadcrumbItemTrigger>{currentBranchName}</BreadcrumbItemTrigger>

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
