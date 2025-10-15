import * as ScrollAreaPrimitive from "@radix-ui/react-scroll-area";
import type * as React from "react";

import { classNames } from "@/shared/utils/common";

export interface ScrollAreaProps
  extends React.ComponentPropsWithoutRef<typeof ScrollAreaPrimitive.Root> {
  scrollX?: boolean;
  scrollY?: boolean;
  scrollBarClassName?: string;
  ref?: React.Ref<HTMLDivElement>;
}

export function ScrollArea({
  className,
  children,
  scrollX = false,
  scrollY = true,
  scrollBarClassName,
  ref,
  ...props
}: ScrollAreaProps) {
  return (
    <ScrollAreaPrimitive.Root
      scrollHideDelay={0}
      className={classNames("relative overflow-hidden", className)}
      {...props}
    >
      <ScrollAreaPrimitive.Viewport className="h-full w-full rounded-[inherit]" ref={ref}>
        {children}
      </ScrollAreaPrimitive.Viewport>
      {scrollX && <ScrollBar orientation="horizontal" className={scrollBarClassName} />}
      {scrollY && <ScrollBar orientation="vertical" className={scrollBarClassName} />}
      <ScrollAreaPrimitive.Corner />
    </ScrollAreaPrimitive.Root>
  );
}

export interface ScrollBarProps extends ScrollAreaPrimitive.ScrollAreaScrollbarProps {}

export function ScrollBar({ className, orientation = "vertical", ...props }: ScrollBarProps) {
  return (
    <ScrollAreaPrimitive.ScrollAreaScrollbar
      orientation={orientation}
      className={classNames(
        "flex touch-none select-none bg-gray-50 transition-colors",
        orientation === "vertical" && "h-full w-2 border-l border-l-transparent p-px",
        orientation === "horizontal" && "h-2 flex-col border-t border-t-transparent p-px",
        className
      )}
      {...props}
    >
      <ScrollAreaPrimitive.ScrollAreaThumb className="relative flex-1 rounded-full bg-gray-200 hover:bg-gray-400" />
    </ScrollAreaPrimitive.ScrollAreaScrollbar>
  );
}
