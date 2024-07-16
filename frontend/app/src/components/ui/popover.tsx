import { classNames } from "@/utils/common";
import * as PopoverPrimitive from "@radix-ui/react-popover";
import * as React from "react";

export const Popover = PopoverPrimitive.Root;

export const PopoverTrigger = PopoverPrimitive.Trigger;

export const PopoverContent = React.forwardRef<
  React.ElementRef<typeof PopoverPrimitive.Content>,
  PopoverPrimitive.PopoverContentProps
>(({ className, align = "center", sideOffset = 4, ...props }, ref) => (
  <PopoverPrimitive.Portal>
    <PopoverPrimitive.Content
      ref={ref}
      align={align}
      sideOffset={sideOffset}
      className={classNames(
        "z-50 rounded-md border p-2 bg-custom-white shadow-xl outline-none text-sm",
        className
      )}
      {...props}
    />
  </PopoverPrimitive.Portal>
));
