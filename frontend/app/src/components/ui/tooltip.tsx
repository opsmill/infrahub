import { classNames } from "@/utils/common";
import * as TooltipPrimitives from "@radix-ui/react-tooltip";
import { ComponentPropsWithoutRef, ReactNode } from "react";

export interface TooltipProps
  extends Omit<ComponentPropsWithoutRef<typeof TooltipPrimitives.Content>, "content"> {
  content?: ReactNode;
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
      <TooltipPrimitives.Root delayDuration={300}>
        <TooltipPrimitives.Trigger asChild>{children}</TooltipPrimitives.Trigger>

        <TooltipPrimitives.Portal>
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
        </TooltipPrimitives.Portal>
      </TooltipPrimitives.Root>
    </TooltipPrimitives.Provider>
  );
}
