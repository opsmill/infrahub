import * as TooltipPrimitives from "@radix-ui/react-tooltip";
import { ComponentPropsWithoutRef } from "react";
import { classNames } from "../../utils/common";

export interface TooltipProps extends ComponentPropsWithoutRef<typeof TooltipPrimitives.Content> {
  enabled?: boolean;
}
export function Tooltip({
  enabled,
  children,
  content,
  className,
  side = "bottom",
  ...props
}: TooltipProps) {
  return (
    <TooltipPrimitives.Provider>
      <TooltipPrimitives.Root delayDuration={0}>
        <TooltipPrimitives.Trigger asChild>{children}</TooltipPrimitives.Trigger>
        <TooltipPrimitives.Content
          side={side}
          className={classNames(
            "bg-gray-600 text-white text-xs font-medium px-3 py-2 rounded-lg shadow-sm z-50",
            !enabled && "hidden",
            className
          )}
          {...props}>
          {content}
        </TooltipPrimitives.Content>
      </TooltipPrimitives.Root>
    </TooltipPrimitives.Provider>
  );
}
