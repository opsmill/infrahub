import { Icon } from "@iconify-icon/react";
import { Button } from "@infrahub/ui";

import { Menu, MenuItem, MenuTrigger } from "@/shared/components/aria/menu";
import { Popover } from "@/shared/components/aria/popover";
import { INFRAHUB_DOC_LOCAL } from "@/shared/config/config";
import { MENU_EXCLUDELIST } from "@/shared/config/constants";

import { getObjectDetailsUrl } from "@/entities/nodes/utils";
import type { ModelSchema } from "@/entities/schema/types";

type SchemaHelpMenuProps = {
  schema: ModelSchema;
};

export const SchemaHelpMenu = ({ schema }: SchemaHelpMenuProps) => {
  const isListViewDisabled = MENU_EXCLUDELIST.includes(schema.kind as string);

  const documentationUrl = schema.documentation
    ? `${INFRAHUB_DOC_LOCAL}${schema.documentation}`
    : INFRAHUB_DOC_LOCAL;

  return (
    <MenuTrigger>
      <Button size="xs" shape="circle" variant="outline" data-testid="schema-help-menu-trigger">
        ?
      </Button>

      <Popover placement="bottom end">
        <Menu data-testid="schema-help-menu-content">
          <MenuItem isDisabled={!schema.documentation} href={documentationUrl} target="_blank">
            <Icon icon="mdi:book-open-variant-outline" className="text-custom-blue-700 text-lg" />
            Documentation
            <Icon icon="mdi:open-in-new" />
          </MenuItem>

          <MenuItem
            isDisabled={isListViewDisabled}
            href={getObjectDetailsUrl(schema.kind as string)}
          >
            <Icon icon="mdi:table-eye" className="text-custom-blue-700 text-lg" />
            Open list view
          </MenuItem>
        </Menu>
      </Popover>
    </MenuTrigger>
  );
};
