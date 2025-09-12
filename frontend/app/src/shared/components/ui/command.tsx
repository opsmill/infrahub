import { Icon } from "@iconify-icon/react";
import { Command as CommandPrimitive } from "cmdk";
import * as React from "react";

import { classNames } from "@/shared/utils/common";

export const Command = React.forwardRef<
  React.ElementRef<typeof CommandPrimitive>,
  React.ComponentPropsWithoutRef<typeof CommandPrimitive>
>(({ className, ...props }, ref) => (
  <CommandPrimitive
    ref={ref}
    className={classNames("flex h-full w-full flex-col outline-hidden", className)}
    {...props}
  />
));

export const CommandInput = React.forwardRef<
  React.ElementRef<typeof CommandPrimitive.Input>,
  React.ComponentPropsWithoutRef<typeof CommandPrimitive.Input>
>(({ className, ...props }, ref) => (
  <div
    className={classNames(
      "flex h-10 shrink-0 items-center border-gray-200 border-b text-neutral-800 outline-hidden",
      className
    )}
  >
    <Icon icon="mdi:search" className="mx-2.5 shrink-0 text-lg" />
    <CommandPrimitive.Input
      ref={ref}
      className="grow border-none bg-transparent pl-0 text-sm outline-hidden placeholder:text-gray-400 disabled:cursor-not-allowed disabled:opacity-50 focus:[box-shadow:none]"
      {...props}
    />
  </div>
));

export const CommandList = React.forwardRef<
  React.ElementRef<typeof CommandPrimitive.List>,
  React.ComponentPropsWithoutRef<typeof CommandPrimitive.List>
>(({ className, ...props }, ref) => (
  <CommandPrimitive.List
    ref={ref}
    className={classNames(
      "max-h-[280px] grow overflow-y-auto overflow-x-hidden rounded-md p-2",
      className
    )}
    asChild
    {...props}
  />
));

export const CommandItem = React.forwardRef<
  React.ElementRef<typeof CommandPrimitive.Item>,
  React.ComponentPropsWithoutRef<typeof CommandPrimitive.Item>
>(({ className, ...props }, ref) => (
  <CommandPrimitive.Item
    ref={ref}
    className={classNames(
      "flex cursor-default select-none items-center gap-2 rounded-md px-2 py-1.5 text-sm outline-hidden",
      "data-[disabled=true]:pointer-events-none data-[selected='true']:bg-gray-100 data-[selected=true]:bg-gray-100 data-[disabled=true]:opacity-50",
      className
    )}
    {...props}
  />
));

export const CommandEmpty = React.forwardRef<
  React.ElementRef<typeof CommandPrimitive.Empty>,
  React.ComponentPropsWithoutRef<typeof CommandPrimitive.Empty>
>((props, ref) => (
  <CommandPrimitive.Empty ref={ref} className="p-2 text-center text-sm" {...props} />
));
