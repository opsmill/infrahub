import * as PopoverPrimitive from "@radix-ui/react-popover";
import * as TabsPrimitive from "@radix-ui/react-tabs";
import React from "react";

import { classNames } from "@/shared/utils/common";

export const Popover = PopoverPrimitive.Root;

export const PopoverTrigger = PopoverPrimitive.Trigger;

export const PopoverAnchor = PopoverPrimitive.Anchor;

interface PopoverContentProps extends React.ComponentProps<typeof PopoverPrimitive.Content> {
  portal?: boolean;
}

export const PopoverContent = ({
  className,
  align = "center",
  sideOffset = 4,
  portal = true,
  ref,
  ...props
}: PopoverContentProps) => {
  const Wrapper = portal ? PopoverPrimitive.Portal : React.Fragment;

  return (
    <Wrapper>
      <PopoverPrimitive.Content
        data-react-aria-top-layer=""
        ref={ref}
        align={align}
        sideOffset={sideOffset}
        className={classNames(
          "z-10 max-w-[100vw] rounded-md border border-gray-200 bg-white p-2 text-sm shadow-xl outline-hidden",
          "data-[state=open]:fade-in-0 data-[state=open]:animate-in",
          "data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95 data-[state=closed]:animate-out",
          "data-[side=bottom]:slide-in-from-top-2 data-[side=left]:slide-in-from-right-2 data-[side=right]:slide-in-from-left-2 data-[side=top]:slide-in-from-bottom-2",
          className
        )}
        {...props}
      />
    </Wrapper>
  );
};

export const PopoverTabs = TabsPrimitive.Root;

interface PopoverTabsListProps extends React.ComponentProps<typeof TabsPrimitive.List> {}

export const PopoverTabsList = ({ className, ref, ...props }: PopoverTabsListProps) => (
  <TabsPrimitive.List
    ref={ref}
    className={classNames(
      "inline-flex w-full items-center justify-center border-gray-200 border-b px-2",
      className
    )}
    {...props}
  />
);

interface PopoverTabsTriggerProps extends React.ComponentProps<typeof TabsPrimitive.Trigger> {}

export const PopoverTabsTrigger = ({ className, ref, ...props }: PopoverTabsTriggerProps) => (
  <TabsPrimitive.Trigger
    ref={ref}
    className={classNames(
      "inline-flex items-center justify-center whitespace-nowrap rounded-t-md bg-white px-3 py-1.5 font-medium text-sm transition-all",
      "outline-hidden",
      "disabled:pointer-events-none disabled:opacity-50",
      "border-gray-200 data-[state=active]:-mb-px data-[state=active]:border-x data-[state=active]:border-t",
      className
    )}
    {...props}
  />
);

interface PopoverTabsContentProps extends React.ComponentProps<typeof TabsPrimitive.Content> {}

export const PopoverTabsContent = ({ className, ref, ...props }: PopoverTabsContentProps) => (
  <TabsPrimitive.Content
    ref={ref}
    tabIndex={-1}
    className={classNames("outline-hidden", className)}
    {...props}
  />
);
