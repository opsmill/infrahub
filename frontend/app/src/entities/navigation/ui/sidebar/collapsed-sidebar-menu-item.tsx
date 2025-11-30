import { Icon } from "@iconify-icon/react";

import { type ButtonProps, ButtonWithTooltip } from "@/shared/components/buttons/button-primitive";
import { classNames } from "@/shared/utils/common";

export interface CollapsedSidebarMenuItemProps extends ButtonProps {
  tooltipContent: string;
  icon: string;
}

export function CollapsedSidebarMenuItem({
  className,
  icon,
  ...props
}: CollapsedSidebarMenuItemProps) {
  return (
    <ButtonWithTooltip
      variant="ghost"
      size="square"
      side="right"
      tooltipEnabled
      className={classNames("h-10 w-10 p-2", className)}
      {...props}
    >
      <Icon icon={icon} className="text-base" />
    </ButtonWithTooltip>
  );
}
