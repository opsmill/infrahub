import { Button, ButtonProps } from "@/components/buttons/button-primitive";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Icon } from "@iconify-icon/react";
import { CopyToClipboard } from "../buttons/copy-to-clipboard";

interface ObjectDetailsButtonProps extends ButtonProps {
  id: string;
  hfid: string;
  className?: string;
}

export const ObjectDetailsButton = ({ id, hfid, ...props }: ObjectDetailsButtonProps) => {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size={"sm"} {...props}>
          <Icon icon={"mdi:dots-vertical"} />
        </Button>
      </DropdownMenuTrigger>

      <DropdownMenuContent align="end" className="z-10">
        <DropdownMenuItem className="p-0">
          <CopyToClipboard size={"default"} className="flex-grow justify-start gap-2 p-2" text={id}>
            Copy ID
          </CopyToClipboard>
        </DropdownMenuItem>

        <DropdownMenuItem className="p-0">
          <CopyToClipboard
            size={"default"}
            className="flex-grow justify-start gap-2 p-2"
            text={hfid}
          >
            Copy HFID
          </CopyToClipboard>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
};
