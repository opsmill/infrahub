import { Tooltip, TooltipProps } from "@/components/ui/tooltip";
import { Button, ButtonProps } from "./button";

interface ButtonWithTooltipProps extends ButtonProps {
  tooltipContent?: TooltipProps["content"];
  tooltipEnabled?: TooltipProps["enabled"];
}

export const ButtonWithTooltip = ({
  tooltipContent,
  tooltipEnabled,
  ...props
}: ButtonWithTooltipProps) => (
  <Tooltip enabled={tooltipEnabled} content={tooltipContent}>
    <Button {...props} />
  </Tooltip>
);
