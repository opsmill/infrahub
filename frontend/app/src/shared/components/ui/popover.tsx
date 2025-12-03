import * as PopoverPrimitive from "@radix-ui/react-popover";
import * as TabsPrimitive from "@radix-ui/react-tabs";
import * as React from "react";

import { classNames } from "@/shared/utils/common";

export const Popover = PopoverPrimitive.Root;

export const PopoverTrigger = PopoverPrimitive.Trigger;

export const PopoverAnchor = PopoverPrimitive.Anchor;

export const PopoverContent = React.forwardRef<
  React.ElementRef<typeof PopoverPrimitive.Content>,
  PopoverPrimitive.PopoverContentProps & { portal?: boolean }
>(({ className, align = "center", sideOffset = 4, portal = true, ...props }, ref) => {
  const Wrapper = portal ? PopoverPrimitive.Portal : React.Fragment;

  return (
    <Wrapper>
      <PopoverPrimitive.Content
        ref={ref}
        align={align}
        sideOffset={sideOffset}
        className={classNames(
          "z-10 max-w-[100vw] rounded-md border border-gray-200 bg-white p-2 text-sm shadow-xl outline-hidden",
          "dark:border-gray-700 dark:bg-gray-800",
          "data-[state=open]:fade-in-0 data-[state=open]:animate-in",
          "data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95 data-[state=closed]:animate-out",
          "data-[side=bottom]:slide-in-from-top-2 data-[side=left]:slide-in-from-right-2 data-[side=right]:slide-in-from-left-2 data-[side=top]:slide-in-from-bottom-2",
          className
        )}
        {...props}
      />
    </Wrapper>
  );
});

export const PopoverTabs = TabsPrimitive.Root;

export const PopoverTabsList = React.forwardRef<
  React.ElementRef<typeof TabsPrimitive.List>,
  React.ComponentPropsWithoutRef<typeof TabsPrimitive.List>
>(({ className, ...props }, ref) => (
  <TabsPrimitive.List
    ref={ref}
    className={classNames(
      "inline-flex w-full items-center justify-center border-gray-200 border-b px-2",
      "dark:border-gray-700",
      className
    )}
    {...props}
  />
));

export const PopoverTabsTrigger = React.forwardRef<
  React.ElementRef<typeof TabsPrimitive.Trigger>,
  React.ComponentPropsWithoutRef<typeof TabsPrimitive.Trigger>
>(({ className, ...props }, ref) => (
  <TabsPrimitive.Trigger
    ref={ref}
    className={classNames(
      "inline-flex items-center justify-center whitespace-nowrap rounded-t-md bg-white px-3 py-1.5 font-medium text-sm transition-all",
      "outline-hidden dark:bg-gray-800",
      "disabled:pointer-events-none disabled:opacity-50",
      "data-[state=active]:-mb-px border-gray-200 data-[state=active]:border-x data-[state=active]:border-t",
      "dark:border-gray-700 dark:data-[state=active]:border-gray-700",
      className
    )}
    {...props}
  />
));

export const PopoverTabsContent = React.forwardRef<
  React.ElementRef<typeof TabsPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof TabsPrimitive.Content>
>(({ className, ...props }, ref) => (
  <TabsPrimitive.Content
    ref={ref}
    tabIndex={-1}
    className={classNames("outline-hidden", className)}
    {...props}
  />
));
