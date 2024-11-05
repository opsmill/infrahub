import { ButtonProps, ButtonWithTooltip } from "@/components/buttons/button-primitive";
import { classNames } from "@/utils/common";
import { Icon } from "@iconify-icon/react";
import { forwardRef } from "react";

export interface CollapsedButton extends ButtonProps {
  tooltipContent: string;
  icon: string;
}

export const CollapsedButton = forwardRef<HTMLButtonElement, CollapsedButton>(
  ({ className, icon, ...props }, ref) => {
    return (
      <ButtonWithTooltip
        ref={ref}
        variant="ghost"
        size="square"
        side="right"
        tooltipEnabled
        className={classNames("w-10 h-10 p-2", className)}
        {...props}
      >
        <Icon icon={icon} className="text-base" />
      </ButtonWithTooltip>
    );
  }
);
