import { Icon } from "@iconify-icon/react";
import { forwardRef } from "react";

import { type ButtonProps, ButtonWithTooltip } from "@/shared/components/buttons/button-primitive";
import { classNames } from "@/shared/utils/common";

export interface CollapsedButton extends ButtonProps {
  tooltipContent: string;
  icon: string;
}

export const CollapsedMenuItem = forwardRef<HTMLButtonElement, CollapsedButton>(
  ({ className, icon, ...props }, ref) => {
    return (
      <ButtonWithTooltip
        ref={ref}
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
);
