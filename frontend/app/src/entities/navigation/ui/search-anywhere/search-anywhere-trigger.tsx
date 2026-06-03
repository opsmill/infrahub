import { Icon } from "@iconify-icon/react";
import { Button, type ButtonProps } from "@infrahub/ui";

import { Tooltip } from "@/shared/components/aria/tooltip";
import { Row } from "@/shared/components/container";
import { useSidebar } from "@/shared/components/layout/sidebar";
import Kbd from "@/shared/components/ui/kbd";
import { classNames } from "@/shared/utils/common";

export function SearchAnywhereTrigger({ className, ...props }: ButtonProps) {
  const { isCollapsed } = useSidebar();

  if (isCollapsed) {
    return (
      <Tooltip message="Search anywhere" placement="right">
        <Button
          variant="outline"
          shape="square"
          aria-label="Search anywhere"
          data-testid="search-anywhere-trigger"
          {...props}
        >
          <Icon icon="mdi:magnify" aria-hidden="true" className="text-base" />
        </Button>
      </Tooltip>
    );
  }

  const command = navigator.userAgent.includes("Macintosh") ? "command" : "ctrl";

  return (
    <Button
      variant="outline"
      className={classNames("px-2 shadow-none", className)}
      data-testid="search-anywhere-trigger"
      {...props}
    >
      <Row className="grow overflow-hidden">
        <Icon icon="mdi:magnify" aria-hidden="true" className="text-base" />
        <span className="truncate text-stone-700 group-data-[state=collapsed]:hidden">Search</span>
      </Row>

      <Kbd keys={command} className="group-data-[state=collapsed]:hidden">
        K
      </Kbd>
    </Button>
  );
}
