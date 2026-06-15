import { Icon } from "@iconify-icon/react";
import { Button, type ButtonProps, Popover } from "@infrahub/ui";

import { constructPath } from "@/shared/api/rest/fetch";
import { Menu, MenuItem, MenuTrigger } from "@/shared/components/aria/menu";
import { INFRAHUB_DOC_LOCAL } from "@/shared/config/config";
import { QSP } from "@/shared/config/qsp";

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
    <MenuTrigger>
      <Button variant="outline" size="xs" shape="circle" {...props}>
        ?
      </Button>

      <Popover placement="bottom end">
        <Menu>
          <MenuItem
            isDisabled={!documentationUrl}
            href={docFullUrl}
            target="_blank"
            rel="noreferrer"
          >
            <Icon icon="mdi:book-open-variant-outline" className="text-lg" />
            Documentation
            <Icon icon="mdi:open-in-new" />
          </MenuItem>

          <MenuItem
            isDisabled={!kind}
            href={constructPath("/schema", [{ name: QSP.KIND, value: kind }])}
          >
            <Icon icon="mdi:code-json" className="text-lg" />
            Schema
          </MenuItem>
        </Menu>
      </Popover>
    </MenuTrigger>
  );
};
