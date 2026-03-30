import { Icon } from "@iconify-icon/react";
import * as DropdownMenuPrimitive from "@radix-ui/react-dropdown-menu";
import { type ComponentPropsWithoutRef, type ElementRef, forwardRef } from "react";

import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/shared/components/ui/accordion";
import { Tooltip, type TooltipProps } from "@/shared/components/ui/tooltip";
import { classNames } from "@/shared/utils/common";

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
          "z-50 min-w-32 space-y-1 overflow-hidden rounded-xl bg-white p-2 shadow-lg",
          "data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95 data-[state=open]:animate-in",
          "data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95 data-[state=closed]:animate-out",
          "data-[side=bottom]:slide-in-from-top-2 data-[side=left]:slide-in-from-right-2 data-[side=right]:slide-in-from-left-2 data-[side=top]:slide-in-from-bottom-2",
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
      "rounded-lg px-2 py-1.5",
      "text-neutral-800 text-sm",
      "relative flex items-center gap-1.5",
      "cursor-pointer outline-hidden focus:bg-neutral-100",
      "data-disabled:pointer-events-none data-disabled:opacity-40",
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

export const DropdownMenuSub = DropdownMenuPrimitive.Sub;

export const DropdownMenuSubTrigger = forwardRef<
  ElementRef<typeof DropdownMenuPrimitive.SubTrigger>,
  ComponentPropsWithoutRef<typeof DropdownMenuPrimitive.SubTrigger>
>(({ className, children, ...props }, ref) => (
  <DropdownMenuPrimitive.SubTrigger
    ref={ref}
    className={classNames(
      "flex cursor-default select-none items-center gap-1.5 rounded-lg p-2 text-sm outline-hidden focus:bg-neutral-100 data-[state=open]:bg-neutral-100",
      className
    )}
    {...props}
  >
    {children}
    <Icon icon="mdi:chevron-right" className="ml-auto text-lg" />
  </DropdownMenuPrimitive.SubTrigger>
));

export const DropdownMenuSubContent = forwardRef<
  ElementRef<typeof DropdownMenuPrimitive.SubContent>,
  ComponentPropsWithoutRef<typeof DropdownMenuPrimitive.SubContent>
>(({ className, ...props }, ref) => (
  <DropdownMenuPrimitive.SubContent
    ref={ref}
    className={classNames(
      "min-w-32 space-y-1 overflow-hidden rounded-xl bg-white p-2 shadow-lg",
      "data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95 data-[state=open]:animate-in",
      "data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95 data-[state=closed]:animate-out",
      "data-[side=bottom]:slide-in-from-top-2 data-[side=left]:slide-in-from-right-2 data-[side=right]:slide-in-from-left-2 data-[side=top]:slide-in-from-bottom-2",
      className
    )}
    {...props}
  />
));

export const DropdownMenuAccordion = forwardRef<
  ElementRef<typeof AccordionItem>,
  ComponentPropsWithoutRef<typeof AccordionItem> & { defaultOpen?: boolean }
>(({ defaultOpen, ...props }, ref) => {
  return (
    <Accordion type="single" collapsible defaultValue={defaultOpen ? props.value : undefined}>
      <AccordionItem {...props} ref={ref} />
    </Accordion>
  );
});

export const DropdownMenuAccordionTrigger = forwardRef<
  ElementRef<typeof DropdownMenuItem>,
  ComponentPropsWithoutRef<typeof AccordionTrigger>
>((props, ref) => {
  return (
    <DropdownMenuItem
      ref={ref}
      onSelect={(e) => {
        e.preventDefault();
      }}
      asChild
    >
      <AccordionTrigger className="font-normal" {...props} />
    </DropdownMenuItem>
  );
});

export const DropdownMenuAccordionContent = AccordionContent;

export interface DropdownMenuItemWithTooltipProps
  extends ComponentPropsWithoutRef<typeof DropdownMenuPrimitive.Item> {
  tooltipContent?: TooltipProps["content"];
  tooltipEnabled?: TooltipProps["enabled"];
  side?: TooltipProps["side"];
}

export const DropdownMenuItemWithTooltip = forwardRef<
  ElementRef<typeof DropdownMenuPrimitive.Item>,
  DropdownMenuItemWithTooltipProps
>(({ tooltipContent, tooltipEnabled, side = "left", disabled, children, ...props }, ref) => {
  return (
    <Tooltip enabled={tooltipEnabled && disabled} content={tooltipContent} side={side}>
      <div>
        <DropdownMenuItem ref={ref} disabled={disabled} {...props}>
          {children}
        </DropdownMenuItem>
      </div>
    </Tooltip>
  );
});
