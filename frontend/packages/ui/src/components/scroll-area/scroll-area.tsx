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
      <ScrollAreaPrimitive.Viewport
<<<<<<< HEAD
        className={cn(
          "size-full rounded-[inherit]",
          // Radix lays the content out as a table that grows to its widest child; without horizontal scrolling it must stay at the area's width.
          !scrollX && "[&>div]:block!"
        )}
||||||| 27ecdf0051
      <ScrollAreaPrimitive.Viewport className="size-full rounded-[inherit]" ref={ref}>
=======
        // `isolate` keeps z-indexed content, such as sticky table cells, from painting over the overlay scrollbars.
        className="isolate size-full rounded-[inherit]"
>>>>>>> origin/stable
        ref={ref}
      >
        {children}
      </ScrollAreaPrimitive.Viewport>
      {scrollX && <ScrollBar orientation="horizontal" className={scrollBarClassName} />}
      {scrollY && <ScrollBar orientation="vertical" className={scrollBarClassName} />}
      <ScrollAreaPrimitive.Corner />
    </ScrollAreaPrimitive.Root>
  );
}
