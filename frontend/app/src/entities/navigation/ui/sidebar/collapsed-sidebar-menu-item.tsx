import { Icon } from "@iconify-icon/react";
<<<<<<< HEAD
import { Button, type ButtonProps, Tooltip } from "@infrahub/ui";
=======
import { Button, type ButtonProps } from "@infrahub/ui";

import { Tooltip } from "@/shared/components/aria/tooltip";
>>>>>>> origin/stable

export interface CollapsedSidebarMenuItemProps extends ButtonProps {
  tooltipContent: string;
  icon: string;
}

export function CollapsedSidebarMenuItem({
  icon,
  tooltipContent,
  ...props
}: CollapsedSidebarMenuItemProps) {
  return (
    <Tooltip message={tooltipContent} placement="right">
      <Button variant="ghost" shape="square" {...props}>
        <Icon icon={icon} className="text-base" />
      </Button>
    </Tooltip>
  );
}
