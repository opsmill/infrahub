import { classNames } from "@/utils/common";
import * as DropdownMenuPrimitive from "@radix-ui/react-dropdown-menu";
import { ComponentPropsWithoutRef, ElementRef, forwardRef } from "react";

export const DropdownMenu = (props: DropdownMenuPrimitive.DropdownMenuProps) => (
  <DropdownMenuPrimitive.Root modal={false} {...props} />
);

export const DropdownMenuTrigger = DropdownMenuPrimitive.Trigger;

export const DropdownMenuContent = forwardRef<
  ElementRef<typeof DropdownMenuPrimitive.Content>,
  ComponentPropsWithoutRef<typeof DropdownMenuPrimitive.Content>
>(({ className, ...props }, ref) => {
  return (
    <DropdownMenuPrimitive.Portal>
      <DropdownMenuPrimitive.Content
        sideOffset={4}
        ref={ref}
        className={classNames(
          " p-2 bg-white rounded-xl shadow-lg min-w-32 overflow-hidden space-y-1",
          className
        )}
        {...props}
      />
    </DropdownMenuPrimitive.Portal>
  );
});

export const DropdownMenuItem = forwardRef<
  ElementRef<typeof DropdownMenuPrimitive.Item>,
  ComponentPropsWithoutRef<typeof DropdownMenuPrimitive.Item>
>(({ className, ...props }, ref) => (
  <DropdownMenuPrimitive.Item
    ref={ref}
    className={classNames(
      "rounded-lg p-2",
      "text-neutral-800 text-sm",
      "relative flex items-center gap-2",
      "cursor-pointer outline-none focus:bg-neutral-100",
      "data-[disabled]:pointer-events-none data-[disabled]:opacity-40",
      className
    )}
    {...props}
  />
));

export const DropdownMenuDivider = forwardRef<
  ElementRef<typeof DropdownMenuPrimitive.Separator>,
  ComponentPropsWithoutRef<typeof DropdownMenuPrimitive.Separator>
>(({ className, ...props }, ref) => (
  <DropdownMenuPrimitive.Separator
    ref={ref}
    className={classNames("-mx-1 my-1 h-px bg-gray-200", className)}
    {...props}
  />
));
