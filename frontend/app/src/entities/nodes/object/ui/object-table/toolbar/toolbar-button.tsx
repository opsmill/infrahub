import { cva, type VariantProps } from "class-variance-authority";
import { Button as AriaButton, type ButtonProps as AriaButtonProps } from "react-aria-components";

import { focusVisibleStyle } from "@/shared/components/aria/style-rac";
import { Tooltip, type TooltipProps } from "@/shared/components/ui/tooltip";
import { classNames } from "@/shared/utils/common";

const toolbarButtonVariants = cva(
  "inline-flex h-7 items-center justify-center gap-1.5 whitespace-nowrap rounded-lg border border-transparent bg-white px-2 py-1 disabled:cursor-not-allowed disabled:opacity-60",
  {
    variants: {
      variant: {
        default: "border-neutral-200 hover:bg-neutral-50",
        danger: "border-red-200 text-red-600 hover:bg-neutral-50",
        ghost: "bg-transparent text-neutral-600 hover:bg-neutral-200/80",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
);

export interface ToolbarButtonProps
  extends AriaButtonProps,
    VariantProps<typeof toolbarButtonVariants> {}

export function ToolbarButton({ className, variant, ...props }: ToolbarButtonProps) {
  return (
    <AriaButton
      className={classNames(focusVisibleStyle, toolbarButtonVariants({ variant }), className)}
      {...props}
    />
  );
}

export interface ToolbarButtonWithTooltipProps extends ToolbarButtonProps {
  tooltipContent?: TooltipProps["content"];
  tooltipEnabled?: TooltipProps["enabled"];
}

export function ToolbarButtonWithTooltip({
  tooltipContent,
  tooltipEnabled,
  isDisabled,
  ...props
}: ToolbarButtonWithTooltipProps) {
  if (isDisabled && tooltipEnabled) {
    return (
      <Tooltip enabled={tooltipEnabled} content={tooltipContent} side="top">
        <span className="inline-flex">
          <ToolbarButton isDisabled={isDisabled} {...props} />
        </span>
      </Tooltip>
    );
  }

  return <ToolbarButton isDisabled={isDisabled} {...props} />;
}
