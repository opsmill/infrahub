import TasksStatusIcon from "@/assets/icons/tasks-status.svg?react";
import { QSP } from "@/config/qsp";
import { constructPath } from "@/shared/api/rest/fetch";
import { Button, ButtonProps } from "@/shared/components/buttons/button-primitive";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/shared/components/ui/dropdown-menu";
import { Icon } from "@iconify-icon/react";
import { Link } from "react-router";
import { CopyToClipboard } from "../buttons/copy-to-clipboard";

export interface ObjectDetailsButtonProps extends ButtonProps {
  id: string;
  hfid?: string;
  className?: string;
}

export const ObjectDetailsButton = ({ id, hfid, children, ...props }: ObjectDetailsButtonProps) => {
  const taskFilter = {
    name: "node__value",
    value: id,
  };

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size={"sm"} {...props}>
          <Icon icon={"mdi:dots-vertical"} />
        </Button>
      </DropdownMenuTrigger>

      <DropdownMenuContent align="end" className="z-10">
        <DropdownMenuItem className="p-0">
          <CopyToClipboard size={"default"} className="grow justify-start gap-2 p-2" text={id}>
            Copy ID
          </CopyToClipboard>
        </DropdownMenuItem>

        {hfid && hfid !== "null" && (
          <DropdownMenuItem className="p-0">
            <CopyToClipboard size={"default"} className="grow justify-start gap-2 p-2" text={hfid}>
              Copy HFID
            </CopyToClipboard>
          </DropdownMenuItem>
        )}

        {children}

        <DropdownMenuItem asChild>
          <Link
            to={constructPath("/tasks", [
              { name: QSP.FILTER, value: JSON.stringify([taskFilter]) },
            ])}
            target="_blank"
            rel="noreferrer"
          >
            <TasksStatusIcon />
            Tasks
            <Icon icon="mdi:open-in-new" />
          </Link>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
};
