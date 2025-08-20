import TasksStatusIcon from "@/assets/icons/tasks-status.svg?react";
import { QSP } from "@/config/qsp";
import { constructPath } from "@/shared/api/rest/fetch";
import {
  CopyToClipboardMenuItem,
  Menu,
  MenuHeader,
  MenuItem,
  MenuPopover,
  MenuSection,
  MenuTrigger,
} from "@/shared/components/aria/menu";
import { Button, ButtonProps } from "@/shared/components/buttons/button-primitive";
import { Icon } from "@iconify-icon/react";
import { Pressable } from "react-aria-components";

export interface ObjectDetailsButtonProps extends ButtonProps {
  id: string;
  hfid?: string | null;
  className?: string;
}

export const ObjectDetailsButton = ({ id, hfid, children, ...props }: ObjectDetailsButtonProps) => {
  const taskFilter = {
    name: "node__value",
    value: id,
  };

  return (
    <MenuTrigger>
      <Pressable>
        <Button variant="ghost" size={"sm"} {...props}>
          <Icon icon={"mdi:dots-vertical"} />
        </Button>
      </Pressable>

      <MenuPopover placement="bottom end">
        <Menu>
          <MenuSection>
            <MenuHeader>Actions</MenuHeader>
            <CopyToClipboardMenuItem textToCopy={id}>Copy ID</CopyToClipboardMenuItem>

            {hfid && hfid !== "null" && (
              <CopyToClipboardMenuItem textToCopy={hfid}>Copy HFID</CopyToClipboardMenuItem>
            )}

            {children}
          </MenuSection>

          <MenuSection>
            <MenuHeader>Go to</MenuHeader>
            <MenuItem
              href={constructPath("/tasks", [
                { name: QSP.FILTER, value: JSON.stringify([taskFilter]) },
              ])}
              target="_blank"
              rel="noreferrer"
            >
              <TasksStatusIcon width="12" height="12" />
              Tasks
              <Icon icon="mdi:open-in-new" />
            </MenuItem>
          </MenuSection>
        </Menu>
      </MenuPopover>
    </MenuTrigger>
  );
};
