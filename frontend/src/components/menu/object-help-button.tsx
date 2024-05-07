import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "../ui/dropdown-menu";
import { Button } from "../buttons/button-primitive";
import { Link } from "react-router-dom";
import { INFRAHUB_DOC_LOCAL } from "../../config/config";
import { Icon } from "@iconify-icon/react";
import { constructPath } from "../../utils/fetch";

type ObjectHelpButtonProps = {
  documentationUrl?: string | null;
  kind?: string | null;
};

export const ObjectHelpButton = ({ documentationUrl, kind }: ObjectHelpButtonProps) => {
  const docFullUrl = documentationUrl
    ? documentationUrl.startsWith("http")
      ? INFRAHUB_DOC_LOCAL
      : `${INFRAHUB_DOC_LOCAL}${documentationUrl}`
    : "";

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" size="icon">
          ?
        </Button>
      </DropdownMenuTrigger>

      <DropdownMenuContent>
        <DropdownMenuItem disabled={!documentationUrl} asChild>
          <Link to={docFullUrl} target="_blank" className="flex gap-2">
            <Icon icon="mdi:book-open-variant-outline" className="text-lg text-custom-blue-700" />
            Documentation
            <Icon icon="mdi:open-in-new" />
          </Link>
        </DropdownMenuItem>

        <DropdownMenuItem asChild>
          <Link
            to={constructPath("/schema", [{ name: "kind", value: kind }])}
            className="flex gap-2">
            <Icon icon="mdi:code-json" className="text-lg text-custom-blue-700" />
            Schema
          </Link>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
};
