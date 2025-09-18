import * as TooltipPrimitives from "@radix-ui/react-tooltip";
import type { ComponentPropsWithoutRef, ReactNode } from "react";

import { classNames } from "@/shared/utils/common";

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
              "z-50 rounded-lg bg-gray-600 px-3 py-2 font-medium text-white text-xs shadow-xs",
              !enabled && "hidden",
              className
            )}
            {...props}
          >
            {content}
          </TooltipPrimitives.Content>
        </TooltipPrimitives.Portal>
      </TooltipPrimitives.Root>
    </TooltipPrimitives.Provider>
  );
}
