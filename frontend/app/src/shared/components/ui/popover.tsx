import * as PopoverPrimitive from "@radix-ui/react-popover";
import React from "react";

import {
  Tabs,
  TabsContent,
  TabsList,
  type TabsListProps,
  TabsTrigger,
  type TabsTriggerProps,
} from "@/shared/components/ui/tabs";
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
          "z-50 max-w-screen rounded-md border bg-popover p-2 text-sm shadow-xl outline-hidden backdrop-blur-lg",
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

/**
 * The shared `Tabs` primitive, dressed for a popover: the strip spans the popover's width and
 * the active trigger takes the popover's own background so it covers the strip's border where
 * it overlaps it. Everything else is the primitive's.
 */
export const PopoverTabs = Tabs;

export const PopoverTabsList = ({ className, ...props }: TabsListProps) => (
  <TabsList className={classNames("w-full justify-center px-2", className)} {...props} />
);

export const PopoverTabsTrigger = ({ className, ...props }: TabsTriggerProps) => (
  <TabsTrigger className={classNames("bg-popover", className)} {...props} />
);

export const PopoverTabsContent = TabsContent;
