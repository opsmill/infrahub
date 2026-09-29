// PROTOTYPE — branch actions in the header, same shape as ObjectDetailsMenu
// (entities/nodes/object/ui/object-details/object-details-menu.tsx). Merge stays in the rail.
import { Button, Menu, MenuItem, MenuSection, MenuTrigger, Popover } from "@infrahub/ui";
import {
  ChevronDownIcon,
  GitBranchIcon,
  GitPullRequestArrowIcon,
  ShieldCheckIcon,
  Trash2Icon,
} from "lucide-react";
import { toast } from "react-toastify";

import TasksStatusIcon from "@/assets/icons/tasks-status.svg?react";

import { CopyToClipboardMenuItem } from "@/shared/components/menu/copy-to-clipboard-menu-item";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";

const info = (m: string) => toast(<Alert type={ALERT_TYPES.INFO} message={`${m} (prototype)`} />);

export function BranchActionsMenu({ branchName }: { branchName: string }) {
  return (
    <MenuTrigger>
      <Button variant="outline" size="sm">
        Actions <ChevronDownIcon className="size-3.5" />
      </Button>
      <Popover placement="bottom end">
        <Menu>
          <MenuSection title="Actions">
            <MenuItem href="/proposed-changes/new">
              <GitPullRequestArrowIcon className="size-4" /> Propose change
            </MenuItem>
            <MenuItem onAction={() => info("Rebase")}>
              <GitBranchIcon className="size-4" /> Rebase
            </MenuItem>
            <MenuItem onAction={() => info("Validate")}>
              <ShieldCheckIcon className="size-4" /> Validate
            </MenuItem>
            <CopyToClipboardMenuItem textToCopy={branchName}>
              Copy branch name
            </CopyToClipboardMenuItem>
          </MenuSection>
          <MenuSection title="Go to">
            <MenuItem href="/tasks">
              <TasksStatusIcon className="size-4" /> Tasks
            </MenuItem>
            <MenuItem href="/proposed-changes">
              <GitPullRequestArrowIcon className="size-4" /> Proposed changes
            </MenuItem>
          </MenuSection>
          <MenuSection title="Manage">
            <MenuItem onAction={() => info("Delete")} className="text-red-500">
              <Trash2Icon className="size-4" /> Delete
            </MenuItem>
          </MenuSection>
        </Menu>
      </Popover>
    </MenuTrigger>
  );
}
