import type * as React from "react";

import * as ScrollAreaPrimitive from "@radix-ui/react-scroll-area";
import { cn } from "tailwind-variants";

interface ScrollBarProps extends ScrollAreaPrimitive.ScrollAreaScrollbarProps {}

function ScrollBar({ className, orientation = "vertical", ...props }: ScrollBarProps) {
  return (
    <ScrollAreaPrimitive.ScrollAreaScrollbar
      orientation={orientation}
      className={cn(
        "flex touch-none rounded-full select-none bg-neutral-100 transition-colors",
        orientation === "vertical" && "h-full w-1",
        orientation === "horizontal" && "h-1 flex-col",
        className,
      )}
      {...props}
    >
      <ScrollAreaPrimitive.ScrollAreaThumb className="relative flex-1 rounded-[inherit] bg-neutral-300" />
    </ScrollAreaPrimitive.ScrollAreaScrollbar>
  );
}

export interface ScrollAreaProps extends ScrollAreaPrimitive.ScrollAreaProps {
  scrollX?: boolean;
  scrollY?: boolean;
  scrollBarClassName?: string;
  ref?: React.Ref<React.ComponentRef<typeof ScrollAreaPrimitive.Viewport>>;
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
      className={cn("relative overflow-hidden", className)}
      {...props}
    >
      <ScrollAreaPrimitive.Viewport className="size-full rounded-[inherit]" ref={ref}>
        {children}
      </ScrollAreaPrimitive.Viewport>
      {scrollX && <ScrollBar orientation="horizontal" className={scrollBarClassName} />}
      {scrollY && <ScrollBar orientation="vertical" className={scrollBarClassName} />}
      <ScrollAreaPrimitive.Corner />
    </ScrollAreaPrimitive.Root>
  );
}
