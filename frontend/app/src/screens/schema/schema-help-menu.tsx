import { Button } from "@/shared/components/buttons/button-primitive";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/shared/components/ui/dropdown-menu";
import { INFRAHUB_DOC_LOCAL } from "@/config/config";
import { MENU_EXCLUDELIST } from "@/config/constants";
import { IModelSchema } from "@/screens/schema/schema.atom";
import { getObjectDetailsUrl2 } from "@/screens/objects/objects";
import { Icon } from "@iconify-icon/react";
import { Link } from "react-router-dom";

type SchemaHelpMenuProps = {
  schema: IModelSchema;
};

export const SchemaHelpMenu = ({ schema }: SchemaHelpMenuProps) => {
  const isListViewDisabled = MENU_EXCLUDELIST.includes(schema.kind as string);

  const documentationUrl = schema.documentation
    ? `${INFRAHUB_DOC_LOCAL}${schema.documentation}`
    : INFRAHUB_DOC_LOCAL;

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button size="icon" variant="outline" data-testid="schema-help-menu-trigger">
          ?
        </Button>
      </DropdownMenuTrigger>

      <DropdownMenuContent data-testid="schema-help-menu-content">
        <DropdownMenuItem disabled={!schema.documentation} asChild>
          <Link to={documentationUrl} target="_blank" className="flex gap-2">
            <Icon icon="mdi:book-open-variant-outline" className="text-lg text-custom-blue-700" />
            Documentation
            <Icon icon="mdi:open-in-new" />
          </Link>
        </DropdownMenuItem>

        <DropdownMenuItem disabled={isListViewDisabled} asChild>
          <Link to={getObjectDetailsUrl2(schema.kind as string)} className="flex gap-2">
            <Icon icon="mdi:table-eye" className="text-lg text-custom-blue-700" />
            Open list view
          </Link>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
};
