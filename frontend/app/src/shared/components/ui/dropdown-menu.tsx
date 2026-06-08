import { Icon } from "@iconify-icon/react";
import * as DropdownMenuPrimitive from "@radix-ui/react-dropdown-menu";
import type React from "react";

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

interface DropdownMenuContentProps
  extends React.ComponentProps<typeof DropdownMenuPrimitive.Content> {}

export const DropdownMenuContent = ({ className, ref, ...props }: DropdownMenuContentProps) => {
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
};

interface DropdownMenuItemProps extends React.ComponentProps<typeof DropdownMenuPrimitive.Item> {}

export const DropdownMenuItem = ({ className, ref, ...props }: DropdownMenuItemProps) => (
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
);

interface DropdownMenuDividerProps
  extends React.ComponentProps<typeof DropdownMenuPrimitive.Separator> {}

export const DropdownMenuDivider = ({ className, ref, ...props }: DropdownMenuDividerProps) => (
  <DropdownMenuPrimitive.Separator
    ref={ref}
    className={classNames("-mx-1 my-1 h-px bg-gray-200", className)}
    {...props}
  />
);

export const DropdownMenuSub = DropdownMenuPrimitive.Sub;

interface DropdownMenuSubTriggerProps
  extends React.ComponentProps<typeof DropdownMenuPrimitive.SubTrigger> {}

export const DropdownMenuSubTrigger = ({
  className,
  children,
  ref,
  ...props
}: DropdownMenuSubTriggerProps) => (
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
);

interface DropdownMenuSubContentProps
  extends React.ComponentProps<typeof DropdownMenuPrimitive.SubContent> {}

export const DropdownMenuSubContent = ({
  className,
  ref,
  ...props
}: DropdownMenuSubContentProps) => (
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
);

interface DropdownMenuAccordionProps extends React.ComponentProps<typeof AccordionItem> {
  defaultOpen?: boolean;
}

export const DropdownMenuAccordion = ({
  defaultOpen,
  ref,
  ...props
}: DropdownMenuAccordionProps) => {
  return (
    <Accordion type="single" collapsible defaultValue={defaultOpen ? props.value : undefined}>
      <AccordionItem {...props} ref={ref} />
    </Accordion>
  );
};

interface DropdownMenuAccordionTriggerProps
  extends Omit<React.ComponentProps<typeof AccordionTrigger>, "ref"> {
  ref?: React.Ref<React.ComponentRef<typeof DropdownMenuItem>>;
}

export const DropdownMenuAccordionTrigger = ({
  ref,
  ...props
}: DropdownMenuAccordionTriggerProps) => {
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
};

export const DropdownMenuAccordionContent = AccordionContent;

export interface DropdownMenuItemWithTooltipProps
  extends React.ComponentProps<typeof DropdownMenuPrimitive.Item> {
  tooltipContent?: TooltipProps["content"];
  tooltipEnabled?: TooltipProps["enabled"];
  side?: TooltipProps["side"];
}

export const DropdownMenuItemWithTooltip = ({
  tooltipContent,
  tooltipEnabled,
  side = "left",
  disabled,
  children,
  ref,
  ...props
}: DropdownMenuItemWithTooltipProps) => {
  return (
    <Tooltip enabled={tooltipEnabled && disabled} content={tooltipContent} side={side}>
      <div>
        <DropdownMenuItem ref={ref} disabled={disabled} {...props}>
          {children}
        </DropdownMenuItem>
      </div>
    </Tooltip>
  );
};
