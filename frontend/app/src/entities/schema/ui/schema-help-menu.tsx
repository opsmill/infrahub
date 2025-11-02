import { Icon } from "@iconify-icon/react";
import { Pressable } from "react-aria-components";

import { INFRAHUB_DOC_LOCAL } from "@/config/config";
import { MENU_EXCLUDELIST } from "@/config/constants";

import { Menu, MenuItem, MenuPopover, MenuTrigger } from "@/shared/components/aria/menu";
import { Button } from "@/shared/components/buttons/button-primitive";

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
      <Pressable>
        <Button size="icon" variant="outline" data-testid="schema-help-menu-trigger">
          ?
        </Button>
      </Pressable>

      <MenuPopover placement="bottom end">
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
      </MenuPopover>
    </MenuTrigger>
  );
};
