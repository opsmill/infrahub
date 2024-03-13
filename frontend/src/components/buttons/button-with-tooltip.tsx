import { Button, ButtonProps } from "./button";
import { Tooltip, TooltipProps } from "../ui/tooltip";

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
