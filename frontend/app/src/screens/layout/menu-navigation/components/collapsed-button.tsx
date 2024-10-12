import { ButtonProps, ButtonWithTooltip } from "@/components/buttons/button-primitive";
import { classNames } from "@/utils/common";
import { Icon } from "@iconify-icon/react";

export interface CollapsedButton extends ButtonProps {
  tooltipContent: string;
  icon: string;
}

export const CollapsedButton = ({ className, icon, ...props }: CollapsedButton) => {
  return (
    <ButtonWithTooltip
      variant="ghost"
      size="square"
      side="right"
      tooltipEnabled
      className={classNames("w-10 h-10", className)}
      {...props}
    >
      <Icon icon={icon} className="text-xl" />
    </ButtonWithTooltip>
  );
};
