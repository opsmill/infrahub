import { Icon } from "@iconify-icon/react";

import { Button, type ButtonProps } from "@/shared/components/aria/button";
import { Tooltip } from "@/shared/components/aria/tooltip";
import { classNames } from "@/shared/utils/common";

export interface CollapsedSidebarMenuItemProps extends ButtonProps {
  tooltipContent: string;
  icon: string;
}

export function CollapsedSidebarMenuItem({
  className,
  icon,
  tooltipContent,
  ...props
}: CollapsedSidebarMenuItemProps) {
  return (
    <Tooltip message={tooltipContent} placement="right">
      <Button
        variant="ghost"
        size="square"
        className={classNames("h-10 w-10 p-2", className)}
        {...props}
      >
        <Icon icon={icon} className="text-base" />
      </Button>
    </Tooltip>
  );
}
