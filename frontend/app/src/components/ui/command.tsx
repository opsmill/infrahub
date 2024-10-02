import * as React from "react";
import { Command as CommandPrimitive } from "cmdk";
import { classNames } from "@/utils/common";
import { Icon } from "@iconify-icon/react";

export const Command = React.forwardRef<
  React.ElementRef<typeof CommandPrimitive>,
  React.ComponentPropsWithoutRef<typeof CommandPrimitive>
>(({ className, ...props }, ref) => (
  <CommandPrimitive
    ref={ref}
    className={classNames("flex h-full w-full flex-col outline-none", className)}
    {...props}
  />
));

export const CommandInput = React.forwardRef<
  React.ElementRef<typeof CommandPrimitive.Input>,
  React.ComponentPropsWithoutRef<typeof CommandPrimitive.Input>
>(({ className, ...props }, ref) => (
  <div
    className={classNames(
      "h-10 flex items-center border-b outline-none text-neutral-800",
      className
    )}>
    <Icon icon="mdi:search" className="mx-2.5 shrink-0 text-lg" />
    <CommandPrimitive.Input
      ref={ref}
      className="bg-transparent flex-grow pl-0 text-sm outline-none border-none focus:[box-shadow:none] placeholder:text-gray-400 disabled:cursor-not-allowed disabled:opacity-50"
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
    className={classNames("flex-grow p-2 rounded-md overflow-y-auto overflow-x-hidden", className)}
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
      "flex items-center gap-2 cursor-default select-none rounded-md px-2 py-1.5 text-sm outline-none data-[selected='true']:bg-gray-100 data-[selected=true]:bg-gray-100 data-[disabled=true]:opacity-50 data-[disabled=true]:pointer-events-none",
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
