import { Button, ButtonProps } from "@/components/buttons/button-primitive";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { INFRAHUB_DOC_LOCAL } from "@/config/config";
import { constructPath } from "@/utils/fetch";
import { Icon } from "@iconify-icon/react";
import { Link } from "react-router-dom";

interface ObjectHelpButtonProps extends ButtonProps {
  className?: string;
  documentationUrl?: string | null;
  kind?: string | null;
}

export const ObjectHelpButton = ({ documentationUrl, kind, ...props }: ObjectHelpButtonProps) => {
  const docFullUrl = documentationUrl
    ? documentationUrl.startsWith("http")
      ? INFRAHUB_DOC_LOCAL
      : `${INFRAHUB_DOC_LOCAL}${documentationUrl}`
    : "";

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" size="icon" {...props}>
          ?
        </Button>
      </DropdownMenuTrigger>

      <DropdownMenuContent align="end" className="z-10">
        <DropdownMenuItem disabled={!documentationUrl} asChild>
          <Link to={docFullUrl} target="_blank" rel="noreferrer">
            <Icon icon="mdi:book-open-variant-outline" className="text-lg" />
            Documentation
            <Icon icon="mdi:open-in-new" />
          </Link>
        </DropdownMenuItem>

        <DropdownMenuItem asChild>
          <Link to={constructPath("/schema", [{ name: "kind", value: kind }])}>
            <Icon icon="mdi:code-json" className="text-lg" />
            Schema
          </Link>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
};
