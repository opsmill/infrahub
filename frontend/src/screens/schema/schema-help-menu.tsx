import { Button } from "../../components/ui/button";
import { Icon } from "@iconify-icon/react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "../../components/ui/dropdown-menu";
import { IModelSchema, menuFlatAtom } from "../../state/atoms/schema.atom";
import { Link } from "react-router-dom";
import { INFRAHUB_DOC_LOCAL } from "../../config/config";
import { constructPath } from "../../utils/fetch";
import { useAtomValue } from "jotai/index";

type SchemaHelpMenuProps = {
  schema: IModelSchema;
};

export const SchemaHelpMenu = ({ schema }: SchemaHelpMenuProps) => {
  const menuItems = useAtomValue(menuFlatAtom);
  const schemaInMenu = menuItems.find(({ title }) => title === schema.label);

  const documentationUrl = schema.documentation
    ? `${INFRAHUB_DOC_LOCAL}${schema.documentation}`
    : INFRAHUB_DOC_LOCAL;

  const objectListUrl = schemaInMenu ? constructPath(schemaInMenu.path) : "";
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

        <DropdownMenuItem disabled={!schemaInMenu} asChild>
          <Link to={objectListUrl} className="flex gap-2">
            <Icon icon="mdi:table-eye" className="text-lg text-custom-blue-700" />
            Open list view
          </Link>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
};
