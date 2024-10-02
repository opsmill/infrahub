import { classNames } from "@/utils/common";
import * as PopoverPrimitive from "@radix-ui/react-popover";
import * as React from "react";

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
          "z-10 rounded-md border p-2 bg-custom-white shadow-xl outline-none text-sm max-w-[100vw]",
          className
        )}
        {...props}
      />
    </Wrapper>
  );
});
