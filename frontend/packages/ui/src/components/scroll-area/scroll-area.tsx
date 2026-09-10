import * as ScrollAreaPrimitive from "@radix-ui/react-scroll-area";
import type * as React from "react";
import { cn } from "tailwind-variants";

interface ScrollBarProps extends ScrollAreaPrimitive.ScrollAreaScrollbarProps {}

function ScrollBar({ className, orientation = "vertical", ...props }: ScrollBarProps) {
  return (
    <ScrollAreaPrimitive.ScrollAreaScrollbar
      orientation={orientation}
      className={cn(
        "flex touch-none select-none rounded-full bg-background/50 transition-colors",
        orientation === "vertical" && "h-full w-1",
        orientation === "horizontal" && "h-1 flex-col",
        className
      )}
      {...props}
    >
      <ScrollAreaPrimitive.ScrollAreaThumb className="relative flex-1 rounded-[inherit] bg-border" />
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
