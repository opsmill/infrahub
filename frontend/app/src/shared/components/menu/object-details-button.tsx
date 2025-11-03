import { Icon } from "@iconify-icon/react";
import { Pressable } from "react-aria-components";

import TasksStatusIcon from "@/assets/icons/tasks-status.svg?react";
import { QSP } from "@/config/qsp";

import { constructPath } from "@/shared/api/rest/fetch";
import {
  CopyToClipboardMenuItem,
  Menu,
  MenuItem,
  MenuPopover,
  MenuSection,
  MenuTrigger,
} from "@/shared/components/aria/menu";
import { Button, type ButtonProps } from "@/shared/components/buttons/button-primitive";

import { useAuth } from "@/entities/authentication/ui/useAuth";

export interface ObjectDetailsButtonProps extends ButtonProps {
  id: string;
  hfid?: string | null;
  objectKind: string;
  className?: string;
}

export const ObjectDetailsButton = ({
  id,
  hfid,
  children,
  objectKind,
  ...props
}: ObjectDetailsButtonProps) => {
  const taskFilter = {
    name: "node__value",
    value: id,
  };

  const { isAuthenticated } = useAuth();

  return (
    <MenuTrigger>
      <Pressable>
        <Button variant="ghost" size={"sm"} {...props}>
          <Icon icon={"mdi:dots-vertical"} />
        </Button>
      </Pressable>

      <MenuPopover placement="bottom end">
        <Menu>
          <MenuSection title="Actions">
            <CopyToClipboardMenuItem textToCopy={id}>Copy ID</CopyToClipboardMenuItem>

            {hfid && hfid !== "null" && (
              <CopyToClipboardMenuItem textToCopy={hfid}>Copy HFID</CopyToClipboardMenuItem>
            )}

            <MenuItem
              href={objectKind ? constructPath(`/objects/${objectKind}/${id}/convert`) : undefined}
              isDisabled={!isAuthenticated}
            >
              <Icon icon="mdi:swap-horizontal" className="size-3" />
              Convert object type
            </MenuItem>

            {children}
          </MenuSection>

          <MenuSection title="Go to">
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
