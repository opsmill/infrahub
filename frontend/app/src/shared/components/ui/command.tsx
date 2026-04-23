import { Icon } from "@iconify-icon/react";
import { Command as CommandPrimitive } from "cmdk";
import type React from "react";

import { classNames } from "@/shared/utils/common";

interface CommandProps extends React.ComponentProps<typeof CommandPrimitive> {}

export function Command({ className, ref, ...props }: CommandProps) {
  return (
    <CommandPrimitive
      ref={ref}
      className={classNames("flex h-full w-full flex-col outline-hidden", className)}
      {...props}
    />
  );
}

interface CommandInputProps extends React.ComponentProps<typeof CommandPrimitive.Input> {}

export function CommandInput({ className, ref, ...props }: CommandInputProps) {
  return (
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
  );
}

interface CommandListProps extends React.ComponentProps<typeof CommandPrimitive.List> {}

export function CommandList({ className, ref, ...props }: CommandListProps) {
  return (
    <CommandPrimitive.List
      ref={ref}
      className={classNames(
        "max-h-[280px] grow overflow-y-auto overflow-x-hidden rounded-md p-2",
        className
      )}
      asChild
      {...props}
    />
  );
}

interface CommandItemProps extends React.ComponentProps<typeof CommandPrimitive.Item> {}

export function CommandItem({ className, ref, ...props }: CommandItemProps) {
  return (
    <CommandPrimitive.Item
      ref={ref}
      className={classNames(
        "flex cursor-default select-none items-center gap-2 rounded-md px-2 py-1.5 text-sm outline-hidden",
        "data-[disabled=true]:pointer-events-none data-[selected='true']:bg-gray-100 data-[selected=true]:bg-gray-100 data-[disabled=true]:opacity-50",
        className
      )}
      {...props}
    />
  );
}

interface CommandEmptyProps extends React.ComponentProps<typeof CommandPrimitive.Empty> {}

export function CommandEmpty({ ref, ...props }: CommandEmptyProps) {
  return <CommandPrimitive.Empty ref={ref} className="p-2 text-center text-sm" {...props} />;
}
